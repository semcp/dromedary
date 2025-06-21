"""
MCP client management for connecting to and managing MCP servers.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    type: str = "stdio"


class ConnectionFactory(Protocol):
    async def create_connection(self, config: MCPServerConfig):
        pass


class StdioConnectionFactory:
    async def create_connection(self, config: MCPServerConfig):
        if config.type != "stdio":
            raise ValueError(f"StdioConnectionFactory cannot handle connection type: {config.type}")
        
        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env
        )
        
        return stdio_client(server_params)


class ServerConnection:
    def __init__(self, config: MCPServerConfig, connection_factory: ConnectionFactory = None):
        self.config = config
        self.name = config.name
        self._connection_factory = connection_factory or StdioConnectionFactory()
        self._session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._tools: Dict[str, Any] = {}

    async def connect(self) -> None:
        if self.is_connected:
            return

        try:
            self._exit_stack = AsyncExitStack()
            
            # Get the context manager from the factory, then enter it
            context_manager = await self._connection_factory.create_connection(self.config)
            read_stream, write_stream = await self._exit_stack.enter_async_context(context_manager)
            
            self._session = ClientSession(read_stream, write_stream)
            await self._exit_stack.enter_async_context(self._session)
            await self._session.initialize()
            
            await self._load_tools()
            
            logger.info(f"Successfully connected to server: {self.name}")
            
        except Exception as e:
            await self._cleanup()
            logger.error(f"Failed to connect to server {self.name}: {e}")
            raise

    async def _load_tools(self) -> None:
        if not self._session:
            return

        tools_result = await self._session.list_tools()
        
        if hasattr(tools_result, 'tools'):
            tools = tools_result.tools
        elif isinstance(tools_result, list):
            tools = tools_result
        else:
            tools = []

        self._tools.clear()
        for tool in tools:
            self._tools[tool.name] = tool
        
        logger.info(f"Server {self.name} loaded {len(self._tools)} tools: {list(self._tools.keys())}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.is_connected:
            raise RuntimeError(f"Server {self.name} is not connected")
        
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found in server {self.name}")

        try:
            result = await self._session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on server {self.name}: {e}")
            raise

    async def disconnect(self) -> None:
        await self._cleanup()
        logger.info(f"Disconnected from server: {self.name}")

    async def _cleanup(self) -> None:
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning(f"Error during cleanup of server {self.name}: {e}")
            finally:
                self._exit_stack = None
        self._session = None
        self._tools.clear()

    @property
    def is_connected(self) -> bool:
        return self._session is not None and self._exit_stack is not None

    @property
    def tools(self) -> Dict[str, Any]:
        return self._tools.copy()

    def get_tool(self, tool_name: str) -> Optional[Any]:
        return self._tools.get(tool_name)


def load_mcp_configs_from_file(config_path: str) -> Dict[str, MCPServerConfig]:
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    
    if not config_data:
        raise ValueError("Config file is empty")
    
    if 'mcpServers' not in config_data:
        raise ValueError("No 'mcpServers' key found in config")
    
    servers_config = config_data['mcpServers']
    server_configs = {}
    
    for server_name, server_config in servers_config.items():
        config = MCPServerConfig(
            name=server_name,
            type=server_config.get('type', 'stdio'),
            command=server_config.get('command', ''),
            args=server_config.get('args', []),
            env=server_config.get('env', {})
        )
        server_configs[server_name] = config
    
    logger.info(f"Loaded configuration for {len(server_configs)} MCP servers")
    return server_configs


class MCPClientManager:
    def __init__(self, config_path: str = "mcp_servers/mcp-servers-config.json", 
                 connection_factory: ConnectionFactory = None):
        self._config_path = config_path
        self._connection_factory = connection_factory or StdioConnectionFactory()
        self._connections: Dict[str, ServerConnection] = {}
        self._tool_to_server_mapping: Dict[str, str] = {}

    async def initialize_from_config(self) -> List[str]:
        server_configs = load_mcp_configs_from_file(self._config_path)
        return await self.initialize_servers(server_configs)

    async def initialize_servers(self, server_configs: Dict[str, MCPServerConfig]) -> List[str]:
        self._connections.clear()
        self._tool_to_server_mapping.clear()
        
        # Create connections for all servers
        temp_connections = {}
        for config in server_configs.values():
            connection = ServerConnection(config, self._connection_factory)
            temp_connections[config.name] = connection

        # Attempt to connect all servers
        connection_tasks = [
            self._connect_server_with_name(server_name, connection) 
            for server_name, connection in temp_connections.items()
        ]
        
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Build new connections dictionary with only successful connections
        successful_connections = {}
        successful_servers = []
        
        for (server_name, connection), result in zip(temp_connections.items(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to initialize server {server_name}: {result}")
                # Ensure cleanup of failed connection
                await connection.disconnect()
            else:
                successful_connections[server_name] = connection
                successful_servers.append(server_name)

        # Replace connections with only successful ones
        self._connections = successful_connections
        
        # Register tools for all successful servers
        for server_name in successful_servers:
            self._register_server_tools(server_name)

        logger.info(f"Successfully initialized {len(successful_servers)} out of {len(server_configs)} servers")
        return successful_servers

    async def _connect_server_with_name(self, server_name: str, connection: ServerConnection) -> None:
        await connection.connect()

    def _register_server_tools(self, server_name: str) -> None:
        connection = self._connections[server_name]
        
        for tool_name in connection.tools:
            if tool_name not in self._tool_to_server_mapping:
                self._tool_to_server_mapping[tool_name] = server_name
            else:
                existing_server = self._tool_to_server_mapping[tool_name]
                logger.warning(
                    f"Tool name conflict: '{tool_name}' exists in both "
                    f"'{existing_server}' and '{server_name}'. Using '{existing_server}' version."
                )
            
            prefixed_name = f"{server_name}.{tool_name}"
            self._tool_to_server_mapping[prefixed_name] = server_name

    def _resolve_tool(self, tool_name: str) -> tuple[ServerConnection, str]:
        """Resolve a tool name to its connection and actual tool name.
        
        Args:
            tool_name: The tool name, possibly prefixed with server name (e.g., "server1.my_tool")
            
        Returns:
            A tuple of (connection, actual_tool_name)
            
        Raises:
            ValueError: If tool is not found
            RuntimeError: If server connection is not active
        """
        if tool_name not in self._tool_to_server_mapping:
            raise ValueError(f"Tool '{tool_name}' not found in any MCP server")
        
        server_name = self._tool_to_server_mapping[tool_name]
        connection = self._connections.get(server_name)
        
        if not connection or not connection.is_connected:
            raise RuntimeError(f"No active connection for server '{server_name}'")
        
        actual_tool_name = tool_name
        if '.' in tool_name and tool_name.startswith(f"{server_name}."):
            actual_tool_name = tool_name.split('.', 1)[1]
        
        return connection, actual_tool_name

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        connection, actual_tool_name = self._resolve_tool(tool_name)
        return await connection.call_tool(actual_tool_name, arguments)

    def get_all_tools(self) -> Dict[str, Any]:
        all_tools = {}
        for connection in self._connections.values():
            if connection.is_connected:
                all_tools.update(connection.tools)
        return all_tools

    def get_tool(self, tool_name: str) -> Optional[Any]:
        try:
            connection, actual_tool_name = self._resolve_tool(tool_name)
            return connection.get_tool(actual_tool_name)
        except (ValueError, RuntimeError):
            return None

    async def shutdown(self) -> None:
        disconnect_tasks = [
            connection.disconnect() 
            for connection in self._connections.values() 
            if connection.is_connected
        ]
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        self._connections.clear()
        self._tool_to_server_mapping.clear()
        logger.info("All MCP connections shutdown")

    def is_connected(self, server_name: str) -> bool:
        connection = self._connections.get(server_name)
        return connection.is_connected if connection else False

    def get_connected_servers(self) -> List[str]:
        return [
            name for name, connection in self._connections.items()
            if connection.is_connected
        ]

    def add_server(self, config: MCPServerConfig) -> None:
        if config.name in self._connections:
            raise ValueError(f"Server '{config.name}' already exists")
        
        connection = ServerConnection(config, self._connection_factory)
        self._connections[config.name] = connection

    async def connect_server(self, server_name: str) -> None:
        if server_name not in self._connections:
            raise ValueError(f"Server '{server_name}' not found")
        
        connection = self._connections[server_name]
        if not connection.is_connected:
            await connection.connect()
            self._register_server_tools(server_name)

    async def disconnect_server(self, server_name: str) -> None:
        if server_name not in self._connections:
            raise ValueError(f"Server '{server_name}' not found")
        
        connection = self._connections[server_name]
        await connection.disconnect()
        
        tools_to_remove = [
            tool_name for tool_name, mapped_server in self._tool_to_server_mapping.items()
            if mapped_server == server_name
        ]
        for tool_name in tools_to_remove:
            del self._tool_to_server_mapping[tool_name] 
