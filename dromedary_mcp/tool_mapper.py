"""
MCP tool mapper for converting MCP tools to Python callable functions.
"""

import logging
from typing import Dict, Any, Callable
from functools import wraps

from .mcp_manager import MCPManager
from .mcp_types import MCPTypeConverter

logger = logging.getLogger(__name__)


class MCPToolMapper:
    """
    Maps MCP tools to Python callable functions using a provided MCPManager.
    """
    
    def __init__(self, manager: MCPManager):
        self.manager = manager
        self.type_converter = MCPTypeConverter()
        self.mapped_functions: Dict[str, Callable] = self._create_function_mappings()
        logger.info(f"Created {len(self.mapped_functions)} tool mappings.")

    def _create_function_mappings(self) -> Dict[str, Callable]:
        """Creates Python callable functions for all MCP tools."""
        all_tools = self.manager.get_all_tools()
        return {
            tool_name: self._create_mapped_function(tool_name, tool)
            for tool_name, tool in all_tools.items()
        }
    
    def _create_mapped_function(self, tool_name: str, tool: Any) -> Callable:
        """Creates a Python callable function for a single MCP tool."""
        
        @wraps(tool)
        def mapped_function(*args, **kwargs):
            """Dynamically generated function that calls an MCP tool."""
            try:
                tool_schema = getattr(tool, 'inputSchema', None)
                mcp_args = self.type_converter.python_args_to_mcp(
                    list(args), kwargs, tool_schema
                )
                
                logger.debug(f"Calling MCP tool '{tool_name}' with args: {mcp_args}")
                mcp_result = self.manager.call_tool_sync(tool_name, mcp_args)
                
                return self.type_converter.mcp_result_to_python(mcp_result)
            except Exception as e:
                logger.error(f"Error calling MCP tool '{tool_name}': {e}")
                raise RuntimeError(f"MCP tool call '{tool_name}' failed.") from e
        
        mapped_function.__name__ = tool_name
        mapped_function.__doc__ = getattr(tool, 'description', 'No description available.')
        mapped_function._mcp_tool = tool
        
        return mapped_function

    def get_function(self, tool_name: str) -> Callable:
        """Gets a mapped function by tool name."""
        if tool_name not in self.mapped_functions:
            raise KeyError(f"Tool '{tool_name}' not found.")
        return self.mapped_functions[tool_name]

    def get_all_functions(self) -> Dict[str, Callable]:
        """Gets all mapped functions."""
        return self.mapped_functions.copy()
        
    def get_function_info(self, tool_name: str) -> Dict[str, Any]:
        """Gets detailed information about a mapped function."""
        function = self.get_function(tool_name)
        tool = function._mcp_tool
        
        return {
            'name': tool_name,
            'description': tool.description,
            'signature': self.type_converter.format_function_signature(tool),
            'schema': tool.inputSchema,
        }

    def has_tool(self, tool_name: str) -> bool:
        """Checks if a tool is available."""
        return tool_name in self.mapped_functions

    def refresh_mappings(self):
        """Refreshes function mappings. Useful if manager reconnects."""
        self.mapped_functions = self._create_function_mappings()
        logger.info(f"Refreshed mappings. {len(self.mapped_functions)} tools available.") 