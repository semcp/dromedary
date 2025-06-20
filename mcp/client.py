"""
MCP client management for connecting to and managing MCP servers.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

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
        self._load_config()
    
    def _load_config(self):
        """Load MCP server configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            for server_name, server_config in config_data.get("mcpServers", {}).items():
                self.servers[server_name] = MCPServerConfig(
                    name=server_name,
                    command=server_config["command"],
                    args=server_config.get("args", []),
                    env=server_config.get("env", {}),
                    type=server_config.get("type", "stdio")
                )
            
            logger.info(f"Loaded {len(self.servers)} MCP server configurations")
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            raise
    
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
            
            read_stream, write_stream = await stdio_client(server_params).__aenter__()
            
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()
            
            self.sessions[server_name] = session
            
            tools = await session.list_tools()
            for tool in tools:
                full_tool_name = f"{server_name}.{tool.name}"
                self.tools[full_tool_name] = tool
                self.server_tool_mapping[full_tool_name] = server_name
                
                if tool.name not in self.tools:
                    self.tools[tool.name] = tool
                    self.server_tool_mapping[tool.name] = server_name
            
            logger.info(f"Server {server_name} loaded {len(tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize server {server_name}: {e}")
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
            actual_tool_name = tool_name
            if '.' in tool_name:
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
        return self.tools.get(tool_name)
    
    async def shutdown(self):
        """Shutdown all MCP server connections."""
        shutdown_tasks = []
        
        for server_name, session in self.sessions.items():
            if session:
                task = asyncio.create_task(self._shutdown_session(session, server_name))
                shutdown_tasks.append(task)
        
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self.sessions.clear()
        self.tools.clear()
        self.server_tool_mapping.clear()
        logger.info("All MCP sessions shutdown")
    
    async def _shutdown_session(self, session: Any, server_name: str):
        """Shutdown a single MCP session."""
        try:
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