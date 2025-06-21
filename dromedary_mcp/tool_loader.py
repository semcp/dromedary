"""
Provides a unified, high-level interface for accessing MCP tools.
"""

import logging
from typing import Dict, Callable, Any, List, Optional

from .tool_mapper import MCPToolMapper
from .mcp_manager import MCPManager

logger = logging.getLogger(__name__)


class MCPToolLoader:
    """A simple, stateless facade for accessing available MCP tools."""
    
    def __init__(self, tool_mapper: MCPToolMapper, manager: MCPManager):
        self._tool_mapper = tool_mapper
        self._manager = manager

    def get_all_tools(self) -> Dict[str, Callable]:
        """Gets all available MCP tools as a dictionary of callable functions."""
        return self._tool_mapper.get_all_functions()
    
    def get_tool_function(self, tool_name: str) -> Callable:
        """
        Gets a specific tool as a callable function.
        
        Raises:
            KeyError: if the tool is not found.
        """
        return self._tool_mapper.get_function(tool_name)
    
    def has_tool(self, tool_name: str) -> bool:
        """Checks if a specific tool is available."""
        return self._tool_mapper.has_tool(tool_name)
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a tool.
        
        Raises:
            KeyError: if the tool is not found.
        """
        return self._tool_mapper.get_function_info(tool_name)
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Gets the schema for a specific tool (for prompt builder compatibility).
        Returns None if the tool does not exist.
        """
        if not self.has_tool(tool_name):
            return None
        
        try:
            tool_info = self.get_tool_info(tool_name)
            return {
                'description': tool_info.get('description', ''),
                'inputSchema': tool_info.get('schema', {})
            }
        except Exception as e:
            logger.warning(f"Could not generate schema for tool {tool_name}: {e}")
            return None
    
    def get_available_tools(self) -> List[str]:
        """Gets a simple list of available tool names."""
        return list(self._tool_mapper.mapped_functions.keys())
    
    def get_available_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """Gets detailed information about all available tools."""
        tools_info = {}
        for tool_name in self._tool_mapper.mapped_functions:
            try:
                tools_info[tool_name] = self.get_tool_info(tool_name)
            except Exception as e:
                logger.warning(f"Could not get info for tool {tool_name}: {e}")
        
        return tools_info
    
    def get_connected_servers(self) -> List[str]:
        """Gets a list of connected MCP server names."""
        return self._manager.get_connected_servers()
    
    def refresh(self) -> bool:
        """Refreshes tool mappings after server reconnection."""
        try:
            self._tool_mapper.refresh_mappings()
            return True
        except Exception as e:
            logger.error(f"Failed to refresh tool mappings: {e}")
            return False


def create_mcp_tool_loader(config_path: str = "mcp_servers/mcp-servers-config.json") -> MCPToolLoader:
    """
    Factory function to create and initialize a fully configured MCPToolLoader.

    This function handles the entire setup process:
    1. Initializes the MCPManager (starts background thread, connects to servers).
    2. Creates the MCPToolMapper with the initialized manager.
    3. Creates the MCPToolLoader with the mapper.

    Args:
        config_path: Path to the MCP servers configuration file.
    
    Returns:
        An initialized and ready-to-use MCPToolLoader instance.
        
    Note: The caller is responsible for the lifecycle of the created manager,
    which is held by the returned loader. For long-running apps, this is fine.
    For short scripts, consider using the MCPManager as a context manager directly.
    """
    logger.info(f"Creating MCP tool loader with config: {config_path}")
    
    manager = MCPManager(config_path)
    manager.initialize()
    
    tool_mapper = MCPToolMapper(manager)
    
    tool_loader = MCPToolLoader(tool_mapper, manager)
    
    logger.info("MCPToolLoader created successfully.")
    return tool_loader


 