"""
Manages a persistent, background-threaded connection to MCP servers.
"""
import asyncio
import logging
import threading
import concurrent.futures
from typing import Dict, Any, List

from .client import MCPClientManager

logger = logging.getLogger(__name__)


class MCPManager:
    """
    Manages MCP sessions in a persistent background thread.

    This class is a context manager to ensure clean startup and shutdown.
    """

    def __init__(self, config_path: str):
        self._config_path = config_path
        self._client_manager: MCPClientManager | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._is_running = False

    def initialize(self, timeout: float = 10.0) -> None:
        """
        Starts the background event loop and initializes MCP connections.
        Blocks until initialization is complete or times out.
        
        Raises:
            RuntimeError: If initialization fails.
            TimeoutError: If initialization takes too long.
        """
        if self._is_running:
            logger.info("MCPManager is already initialized.")
            return

        init_future = concurrent.futures.Future()
        
        def run_persistent_loop():
            nonlocal init_future
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                
                async def init_mcp():
                    try:
                        self._client_manager = MCPClientManager(self._config_path)
                        servers = await self._client_manager.initialize_from_config()
                        
                        if not servers:
                            raise RuntimeError("Failed to connect to any MCP servers.")
                        
                        logger.info(f"MCPManager initialized with {len(servers)} servers.")
                        init_future.set_result(True)
                    except Exception as e:
                        logger.error(f"MCP initialization failed in background thread: {e}")
                        init_future.set_exception(e)
                
                self._loop.create_task(init_mcp())
                self._loop.run_forever()
            finally:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
                logger.info("MCPManager event loop has stopped.")

        self._thread = threading.Thread(target=run_persistent_loop, daemon=True)
        self._thread.start()
        self._is_running = True

        try:
            init_future.result(timeout=timeout)
        except (Exception, concurrent.futures.TimeoutError) as e:
            self._is_running = False
            raise RuntimeError(f"Failed to initialize MCPManager: {e}") from e

    def shutdown(self, timeout: float = 5.0) -> None:
        """Stops the background event loop and shuts down connections."""
        if not self._is_running:
            return
            
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            
        if self._thread:
            self._thread.join(timeout=timeout)
            
        self._is_running = False
        logger.info("MCPManager shutdown complete.")

    def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Any:
        """Executes an MCP tool synchronously by delegating to the background loop."""
        if not self._is_running or not self._loop:
            raise RuntimeError("MCPManager is not running.")
        
        future = asyncio.run_coroutine_threadsafe(
            self._client_manager.call_tool(tool_name, arguments), self._loop
        )
        
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"MCP tool call '{tool_name}' timed out after {timeout}s.")
        except Exception as e:
            raise RuntimeError(f"An error occurred while calling tool '{tool_name}': {e}") from e

    def get_all_tools(self) -> Dict[str, Any]:
        """Gets all available tools from the connected servers."""
        if not self._is_running or not self._client_manager:
            return {}
        return self._client_manager.get_all_tools()

    def get_connected_servers(self) -> List[str]:
        """Gets the names of all successfully connected servers."""
        if not self._is_running or not self._client_manager:
            return []
        return self._client_manager.get_connected_servers()
    
    def __enter__(self):
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown() 