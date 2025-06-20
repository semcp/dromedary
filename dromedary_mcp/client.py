"""
MCP client management for connecting to and managing MCP servers.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import AsyncExitStack

# Import from external MCP SDK with specific paths to avoid circular imports
try:
    from mcp import ClientSession, StdioServerParameters, stdio_client, types as mcp_types
except ImportError:
    # Fallback imports for testing
    ClientSession = Any
    StdioServerParameters = Any
    stdio_client = None
    mcp_types = None

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    type: str = "stdio"


class MCPClientManager:
    """Manages connections to multiple MCP servers."""
    
    def __init__(self, config_path: str = "mcp_servers/mcp-servers-config.json"):
        self.config_path = Path(config_path)
        self.servers: Dict[str, MCPServerConfig] = {}
        self.sessions: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        self.server_tool_mapping: Dict[str, str] = {}
        self.exit_stacks: Dict[str, AsyncExitStack] = {}
        self._load_config()
    
    def _load_config(self):
        """Load MCP server configuration from JSON file."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found: {self.config_path}")
                return
                
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            if 'mcpServers' not in config_data:
                logger.warning("No 'mcpServers' key found in config")
                return
            
            servers_config = config_data['mcpServers']
            
            for server_name, server_config in servers_config.items():
                server = MCPServerConfig(
                    name=server_name,
                    type=server_config.get('type', 'stdio'),
                    command=server_config.get('command', ''),
                    args=server_config.get('args', []),
                    env=server_config.get('env', {})
                )
                self.servers[server_name] = server
                
            logger.info(f"Loaded config for {len(self.servers)} MCP servers")
            
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error(f"Failed to load MCP config: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading MCP config: {e}")
    
    async def initialize_all_servers(self):
        """Initialize connections to all configured MCP servers."""
        initialization_tasks = []
        
        for server_name in self.servers:
            task = asyncio.create_task(self._initialize_server(server_name))
            initialization_tasks.append(task)
        
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)
        
        successful_servers = []
        for i, result in enumerate(results):
            server_name = list(self.servers.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Failed to initialize server {server_name}: {result}")
            else:
                successful_servers.append(server_name)
                logger.info(f"Successfully initialized server: {server_name}")
        
        logger.info(f"Initialized {len(successful_servers)} out of {len(self.servers)} servers")
        return successful_servers
    
    async def _initialize_server(self, server_name: str):
        """Initialize a single MCP server connection."""
        if stdio_client is None or ClientSession is None:
            raise RuntimeError("MCP SDK not available for server initialization")
            
        server_config = self.servers[server_name]
        
        try:
            server_params = StdioServerParameters(
                command=server_config.command,
                args=server_config.args,
                env=server_config.env
            )
            
            # Use AsyncExitStack to properly manage async context managers
            exit_stack = AsyncExitStack()
            self.exit_stacks[server_name] = exit_stack
            
            # Enter the stdio_client context
            stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
            read_stream, write_stream = stdio_transport
            
            # Create and initialize session
            session = ClientSession(read_stream, write_stream)
            await exit_stack.enter_async_context(session)
            await session.initialize()
            
            self.sessions[server_name] = session
            
            tools_result = await session.list_tools()
            # Handle both mock objects and real MCP responses
            if hasattr(tools_result, 'tools'):
                tools = tools_result.tools
            elif isinstance(tools_result, list):
                tools = tools_result
            else:
                tools = []
            logger.info(f"Server {server_name} returned {len(tools)} tools: {[tool.name for tool in tools]}")
            for tool in tools:
                # Store tool with just the name (no duplicates)
                if tool.name not in self.tools:
                    self.tools[tool.name] = tool
                    self.server_tool_mapping[tool.name] = server_name
                else:
                    # Handle naming conflicts by preferring the first registered tool
                    # but log a warning about the conflict
                    existing_server = self.server_tool_mapping[tool.name]
                    logger.warning(f"Tool name conflict: '{tool.name}' exists in both '{existing_server}' and '{server_name}'. Using '{existing_server}' version.")
                
                # Also map the prefixed version for backwards compatibility
                # but don't store it in the tools dict to avoid duplication in display
                prefixed_name = f"{server_name}.{tool.name}"
                self.server_tool_mapping[prefixed_name] = server_name
            
            logger.info(f"Server {server_name} loaded {len(tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize server {server_name}: {e}")
            # Clean up the exit stack if initialization failed
            if server_name in self.exit_stacks:
                try:
                    await self.exit_stacks[server_name].aclose()
                except Exception:
                    pass
                del self.exit_stacks[server_name]
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool through the appropriate MCP server."""
        if tool_name not in self.server_tool_mapping:
            raise ValueError(f"Tool '{tool_name}' not found in any MCP server")
        
        server_name = self.server_tool_mapping[tool_name]
        session = self.sessions.get(server_name)
        
        if not session:
            raise RuntimeError(f"No active session for server '{server_name}'")
        
        try:
            # Strip server prefix from tool name when calling the session
            actual_tool_name = tool_name
            if '.' in tool_name and tool_name.startswith(f"{server_name}."):
                actual_tool_name = tool_name.split('.', 1)[1]
            
            result = await session.call_tool(actual_tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
    
    def get_all_tools(self) -> Dict[str, Any]:
        """Get all available tools from all connected servers."""
        return self.tools.copy()
    
    def get_tool(self, tool_name: str) -> Optional[Any]:
        """Get a specific tool by name."""
        # First try the direct lookup
        tool = self.tools.get(tool_name)
        if tool:
            return tool
        
        # If not found and it's a prefixed name, try without the prefix
        if '.' in tool_name and tool_name in self.server_tool_mapping:
            server_name = self.server_tool_mapping[tool_name]
            if tool_name.startswith(f"{server_name}."):
                actual_tool_name = tool_name.split('.', 1)[1]
                return self.tools.get(actual_tool_name)
        
        return None
    
    async def shutdown(self):
        """Shutdown all MCP server connections."""
        shutdown_tasks = []
        
        for server_name in list(self.exit_stacks.keys()):
            task = asyncio.create_task(self._shutdown_session(server_name))
            shutdown_tasks.append(task)
        
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self.sessions.clear()
        self.tools.clear()
        self.server_tool_mapping.clear()
        self.exit_stacks.clear()
        logger.info("All MCP sessions shutdown")
    
    async def _shutdown_session(self, server_name: str):
        """Shutdown a single MCP session."""
        try:
            if server_name in self.exit_stacks:
                await self.exit_stacks[server_name].aclose()
            # Also call __aexit__ on the session for compatibility with tests
            if server_name in self.sessions:
                session = self.sessions[server_name]
                if hasattr(session, '__aexit__'):
                    await session.__aexit__(None, None, None)
            logger.info(f"Shutdown session for server: {server_name}")
        except Exception as e:
            logger.error(f"Error shutting down session {server_name}: {e}")
    
    def is_connected(self, server_name: str) -> bool:
        """Check if a server is connected."""
        return server_name in self.sessions
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        return list(self.sessions.keys()) 