"""
MCP tool loader that provides a unified interface for loading and executing MCP tools.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Callable, Any, Optional, List

from .client import MCPClientManager
from .tool_mapper import MCPToolMapper, initialize_persistent_mcp_manager, shutdown_persistent_mcp_manager, _persistent_mcp_manager

logger = logging.getLogger(__name__)


class MCPToolLoader:
    """Unified interface for loading and executing MCP tools."""
    
    def __init__(self, config_path: str = "mcp_servers/mcp-servers-config.json"):
        self.config_path = config_path
        self.tool_mapper: Optional[MCPToolMapper] = None
        self._is_initialized = False
    
    async def initialize(self) -> bool:
        """Initialize MCP connections and tool mappings (async version for compatibility)."""
        return self.initialize_sync()
    
    def initialize_sync(self) -> bool:
        """Initialize MCP connections synchronously using the persistent manager."""
        if self._is_initialized:
            return True
            
        logger.info("Initializing MCP tool loader...")
        
        try:
            # Initialize the persistent MCP manager
            success = initialize_persistent_mcp_manager(self.config_path)
            
            if not success:
                logger.error("Failed to initialize persistent MCP manager")
                return False
            
            # Create tool mapper using the persistent manager
            self.tool_mapper = MCPToolMapper()
            self._is_initialized = True
            
            logger.info(f"MCP tool loader initialized with {len(self.tool_mapper.mapped_functions)} tools")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP tool loader: {e}")
            return False
    
    def is_initialized(self) -> bool:
        """Check if the loader is initialized."""
        return self._is_initialized
    
    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all available MCP tools as callable functions."""
        if not self._is_initialized:
            raise RuntimeError("MCPToolLoader not initialized. Call initialize() first.")
        return self.tool_mapper.get_all_functions()
    
    def get_tool_function(self, tool_name: str) -> Callable:
        """Get a specific tool as a callable function."""
        if not self._is_initialized:
            raise RuntimeError("MCPToolLoader not initialized. Call initialize() first.")
        return self.tool_mapper.get_function(tool_name)
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        if not self._is_initialized:
            return False
        return self.tool_mapper.has_tool(tool_name)
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Get information about a tool."""
        if not self._is_initialized:
            raise RuntimeError("MCPToolLoader not initialized. Call initialize() first.")
        return self.tool_mapper.get_function_info(tool_name)
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific tool (for prompt builder compatibility)."""
        if not self._is_initialized:
            return None
        
        try:
            tool_info = self.get_tool_info(tool_name)
            # Convert tool info to schema format expected by prompt builder
            return {
                'description': tool_info.get('description', ''),
                'inputSchema': tool_info.get('schema', {})
            }
        except Exception as e:
            logger.warning(f"Could not get schema for tool {tool_name}: {e}")
            return None
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names (simplified for display)."""
        if not self._is_initialized:
            return []
        
        return list(self.tool_mapper.mapped_functions.keys())
    
    def get_available_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed information about all available tools."""
        if not self._is_initialized:
            return {}
        
        tools_info = {}
        for tool_name in self.tool_mapper.mapped_functions:
            try:
                tools_info[tool_name] = self.get_tool_info(tool_name)
            except Exception as e:
                logger.warning(f"Could not get info for tool {tool_name}: {e}")
        
        return tools_info
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected MCP servers with actual server names."""
        if not self._is_initialized:
            return []
        
        # Get actual server names from the persistent manager
        tools = _persistent_mcp_manager.get_all_tools()
        if tools and hasattr(_persistent_mcp_manager, '_client_manager') and _persistent_mcp_manager._client_manager:
            # Try to get real server names from the client manager
            client_manager = _persistent_mcp_manager._client_manager
            if hasattr(client_manager, 'sessions') and client_manager.sessions:
                return list(client_manager.sessions.keys())
        
        return []
    
    async def shutdown(self):
        """Shutdown MCP connections (async version for compatibility)."""
        self.shutdown_sync()
    
    def shutdown_sync(self):
        """Shutdown MCP connections synchronously."""
        if not self._is_initialized:
            return
        
        shutdown_persistent_mcp_manager()
        self._is_initialized = False
        logger.info("MCP tool loader shutdown")
    
    def refresh(self) -> bool:
        """Refresh tool mappings after server reconnection."""
        if not self._is_initialized:
            return False
        
        try:
            self.tool_mapper.refresh_mappings()
            return True
        except Exception as e:
            logger.error(f"Failed to refresh tool mappings: {e}")
            return False


def create_mcp_tool_loader(config_path: str = "mcp_servers/mcp-servers-config.json") -> MCPToolLoader:
    """Factory function to create an MCP tool loader."""
    return MCPToolLoader(config_path) 