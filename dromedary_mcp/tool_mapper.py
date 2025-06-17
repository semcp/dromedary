"""
MCP tool mapper for converting MCP tools to Python callable functions.
"""

import asyncio
import logging
import threading
import time
import concurrent.futures
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from functools import wraps

from .client import MCPClientManager, mcp_types
from .types import MCPTypeConverter

logger = logging.getLogger(__name__)


class PersistentMCPManager:
    """Manages MCP sessions in a persistent thread with its own event loop."""
    
    def __init__(self):
        self._loop = None
        self._thread = None
        self._client_manager = None
        self._initialized = False
        self._shutdown = False
        self._init_future = None
        self._config_path = None
        
    def start_and_initialize(self, config_path: str):
        """Start the manager thread and initialize MCP connections."""
        if self._thread is not None and self._initialized:
            return True
            
        # Reset state if previously shut down
        if self._shutdown:
            self._shutdown = False
            self._initialized = False
            self._thread = None
            self._loop = None
            
        self._config_path = config_path
        self._init_future = concurrent.futures.Future()
        
        def run_persistent_loop():
            """Run the persistent event loop with MCP sessions."""
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                
                # Initialize MCP in this loop
                async def init_mcp():
                    try:
                        self._client_manager = MCPClientManager(config_path)
                        successful_servers = await self._client_manager.initialize_all_servers()
                        
                        if successful_servers:
                            self._initialized = True
                            self._init_future.set_result(True)
                            logger.info(f"MCP manager initialized with {len(successful_servers)} servers")
                        else:
                            self._init_future.set_result(False)
                            logger.error("Failed to initialize any MCP servers")
                    except Exception as e:
                        logger.error(f"MCP initialization failed: {e}")
                        self._init_future.set_exception(e)
                
                # Start initialization
                self._loop.create_task(init_mcp())
                
                # Run the loop until shutdown
                self._loop.run_forever()
                
            except Exception as e:
                logger.error(f"Persistent loop error: {e}")
                if not self._init_future.done():
                    self._init_future.set_exception(e)
            finally:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
        
        self._thread = threading.Thread(target=run_persistent_loop, daemon=True)
        self._thread.start()
        
        # Wait for initialization to complete
        try:
            return self._init_future.result(timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to initialize MCP manager: {e}")
            return False
    
    def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any], timeout=30.0):
        """Call an MCP tool synchronously."""
        # Auto-reinitialize if needed
        if not self._initialized and not self._shutdown and self._config_path:
            logger.info("Auto-reinitializing MCP manager...")
            if not self.start_and_initialize(self._config_path):
                raise RuntimeError("Failed to auto-reinitialize MCP manager")
        
        if not self._initialized or self._shutdown:
            raise RuntimeError("MCP manager not initialized or shut down")
        
        # Create a future for the result
        result_future = concurrent.futures.Future()
        
        async def do_call():
            try:
                result = await self._client_manager.call_tool(tool_name, arguments)
                self._loop.call_soon_threadsafe(lambda: result_future.set_result(result))
            except Exception as e:
                exc = e
                self._loop.call_soon_threadsafe(lambda: result_future.set_exception(exc))
        
        # Schedule the call in the MCP loop
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(do_call(), self._loop)
        else:
            raise RuntimeError("MCP event loop is not available")
        
        # Wait for result
        try:
            return result_future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"MCP tool call timed out after {timeout} seconds")
    
    def get_all_tools(self) -> Dict[str, Any]:
        """Get all available tools."""
        # Auto-reinitialize if needed
        if not self._initialized and not self._shutdown and self._config_path:
            logger.info("Auto-reinitializing MCP manager for tool list...")
            if not self.start_and_initialize(self._config_path):
                return {}
                
        if not self._initialized:
            return {}
        return self._client_manager.get_all_tools() if self._client_manager else {}
    
    def shutdown(self):
        """Shutdown the MCP manager."""
        self._shutdown = True
        self._initialized = False
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)

# Global persistent MCP manager
_persistent_mcp_manager = PersistentMCPManager()


class MCPToolMapper:
    """Maps MCP tools to Python callable functions using persistent MCP manager."""
    
    def __init__(self, client_manager: MCPClientManager = None):
        # For backward compatibility, we accept client_manager but use the persistent manager
        self.type_converter = MCPTypeConverter()
        self.mapped_functions: Dict[str, Callable] = {}
        self._create_function_mappings()
    
    def _create_function_mappings(self):
        """Create Python callable functions for all MCP tools."""
        all_tools = _persistent_mcp_manager.get_all_tools()
        
        for tool_name, tool in all_tools.items():
            mapped_function = self._create_mapped_function(tool_name, tool)
            self.mapped_functions[tool_name] = mapped_function
        
        logger.info(f"Created {len(self.mapped_functions)} tool mappings")
    
    def _create_mapped_function(self, tool_name: str, tool: Any) -> Callable:
        """Create a Python callable function for an MCP tool."""
        
        @wraps(tool)
        def mapped_function(*args, **kwargs):
            """Dynamically generated function that calls MCP tool."""
            try:
                # Pass the tool schema to the converter
                tool_schema = getattr(tool, 'inputSchema', None)
                mcp_args = self.type_converter.python_args_to_mcp(list(args), kwargs, tool_schema)
                
                logger.debug(f"Calling MCP tool {tool_name} with args: {mcp_args}")
                mcp_result = _persistent_mcp_manager.call_tool_sync(tool_name, mcp_args, timeout=30.0)
                
                return self.type_converter.mcp_result_to_python(mcp_result)
                
            except Exception as e:
                logger.error(f"Error calling MCP tool {tool_name}: {e}")
                raise RuntimeError(f"MCP tool call failed: {e}") from e
        
        mapped_function.__name__ = tool_name
        mapped_function.__doc__ = tool.description
        mapped_function._mcp_tool = tool
        
        return mapped_function
    
    def get_function(self, tool_name: str) -> Callable:
        """Get a mapped function by tool name."""
        if tool_name not in self.mapped_functions:
            raise ValueError(f"Tool '{tool_name}' not found")
        return self.mapped_functions[tool_name]
    
    def get_all_functions(self) -> Dict[str, Callable]:
        """Get all mapped functions."""
        return self.mapped_functions.copy()
    
    def get_function_info(self, tool_name: str) -> Dict[str, Any]:
        """Get information about a mapped function."""
        if tool_name not in self.mapped_functions:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        function = self.mapped_functions[tool_name]
        tool = function._mcp_tool
        
        return {
            'name': tool_name,
            'description': tool.description,
            'signature': self.type_converter.format_function_signature(tool),
            'schema': tool.inputSchema,
            'server': 'persistent_manager'  # Since we use persistent manager
        }
    
    def refresh_mappings(self):
        """Refresh function mappings after servers are reconnected."""
        self.mapped_functions.clear()
        self._create_function_mappings()
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        return tool_name in self.mapped_functions


def initialize_persistent_mcp_manager(config_path: str) -> bool:
    """Initialize the global persistent MCP manager."""
    return _persistent_mcp_manager.start_and_initialize(config_path)


def shutdown_persistent_mcp_manager():
    """Shutdown the global persistent MCP manager."""
    _persistent_mcp_manager.shutdown()


class AsyncToSyncBridge:
    """Legacy helper class for backward compatibility."""
    
    @staticmethod
    def run_async_safely(coro):
        """Run an async coroutine safely (legacy method)."""
        # This is now deprecated since we use persistent manager
        raise RuntimeError("AsyncToSyncBridge is deprecated, use persistent MCP manager")
    
    @staticmethod
    def run_async_in_sync(coro):
        """Legacy method for backward compatibility."""
        return AsyncToSyncBridge.run_async_safely(coro) 