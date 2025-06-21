import unittest
import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import shutil

from dromedary.mcp.client import MCPServerConfig, ServerConnection, MCPClientManager

class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases."""
    
    def run_async(self, coro):
        """Helper to run async test methods."""
        if asyncio.iscoroutinefunction(coro):
            return asyncio.run(coro())
        return coro


class TestMCPServerConfig(unittest.TestCase):
    """Test MCP server configuration."""
    
    def test_server_config_creation(self):
        """Test creating server configuration."""
        config = MCPServerConfig(
            name="test-server",
            command="python",
            args=["server.py"],
            env={"PATH": "/usr/bin"},
            type="stdio"
        )
        
        self.assertEqual(config.name, "test-server")
        self.assertEqual(config.command, "python")
        self.assertEqual(config.args, ["server.py"])
        self.assertEqual(config.env, {"PATH": "/usr/bin"})
        self.assertEqual(config.type, "stdio")
    
    def test_server_config_default_type(self):
        """Test default server configuration type."""
        config = MCPServerConfig(
            name="test-server",
            command="python",
            args=["server.py"],
            env={}
        )
        
        self.assertEqual(config.type, "stdio")


class TestMCPClientManager(AsyncTestCase):
    """Test MCP client manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test-config.json"
        
        # Create test configuration
        self.test_config = {
            "mcpServers": {
                "test-server-1": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["server1.py"],
                    "env": {"VAR1": "value1"}
                },
                "test-server-2": {
                    "type": "stdio",
                    "command": "uv",
                    "args": ["run", "server2.py"],
                    "env": {}
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(self.test_config, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.config_file.exists():
            self.config_file.unlink()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_config_success(self):
        """Test successful configuration loading."""
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        configs = load_mcp_configs_from_file(str(self.config_file))
        
        self.assertEqual(len(configs), 2)
        
        server1 = configs["test-server-1"]
        self.assertEqual(server1.name, "test-server-1")
        self.assertEqual(server1.command, "python")
        self.assertEqual(server1.args, ["server1.py"])
        self.assertEqual(server1.env, {"VAR1": "value1"})
        
        server2 = configs["test-server-2"]
        self.assertEqual(server2.name, "test-server-2")
        self.assertEqual(server2.command, "uv")
        self.assertEqual(server2.args, ["run", "server2.py"])
        self.assertEqual(server2.env, {})
    
    def test_load_config_file_not_found(self):
        """Test configuration loading with missing file."""
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        with self.assertRaises(FileNotFoundError):
            load_mcp_configs_from_file("nonexistent-config.json")
    
    def test_load_config_invalid_json(self):
        """Test configuration loading with invalid JSON."""
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        invalid_config_file = Path(self.temp_dir) / "invalid-config.json"
        with open(invalid_config_file, 'w') as f:
            f.write("invalid json content")
        
        with self.assertRaises(ValueError):
            load_mcp_configs_from_file(str(invalid_config_file))
        
        invalid_config_file.unlink()
    
    def test_load_config_empty_servers(self):
        """Test configuration loading with empty mcpServers."""
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        empty_config = {"mcpServers": {}}
        empty_config_file = Path(self.temp_dir) / "empty-config.json"
        
        with open(empty_config_file, 'w') as f:
            json.dump(empty_config, f)
        
        configs = load_mcp_configs_from_file(str(empty_config_file))
        self.assertEqual(len(configs), 0)
        
        empty_config_file.unlink()
    
    def test_load_config_missing_mcp_servers(self):
        """Test configuration loading without mcpServers key."""
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        config_without_servers = {"someOtherConfig": "value"}
        config_file = Path(self.temp_dir) / "no-servers-config.json"
        
        with open(config_file, 'w') as f:
            json.dump(config_without_servers, f)
        
        with self.assertRaises(ValueError):
            load_mcp_configs_from_file(str(config_file))
        
        config_file.unlink()
    
    @patch('dromedary.mcp.client.ClientSession')
    @patch('dromedary.mcp.client.StdioServerParameters')
    @patch('dromedary.mcp.client.stdio_client')
    def test_initialize_server_success(self, mock_stdio_client, mock_params, mock_session):
        """Test successful server initialization."""
        
        # Setup mocks
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        def mock_stdio_func(*args, **kwargs):
            return mock_context
        mock_stdio_client.side_effect = mock_stdio_func
        
        mock_session_instance = AsyncMock()
        mock_session_instance.initialize = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        
        # Mock tools
        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool2 = Mock()
        mock_tool2.name = "tool2"
        
        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])
        mock_session.return_value = mock_session_instance
        
        config = MCPServerConfig(
            name="test-server-1",
            command="python",
            args=["server1.py"],
            env={"VAR1": "value1"},
            type="stdio"
        )
        
        # Test single server connection
        async def _test():
            connection = ServerConnection(config)
            await connection.connect()
            
            # Verify connection is established
            self.assertTrue(connection.is_connected)
            self.assertIn("tool1", connection.tools)
            self.assertIn("tool2", connection.tools)
            
            await connection.disconnect()
            self.assertFalse(connection.is_connected)
        
        self.run_async(_test)
        
        # Verify session was created and initialized
        mock_session.assert_called_once()
        mock_session_instance.initialize.assert_called_once()
        mock_session_instance.list_tools.assert_called_once()
    
    @patch('dromedary.mcp.client.ClientSession')
    @patch('dromedary.mcp.client.StdioServerParameters')
    @patch('dromedary.mcp.client.stdio_client')
    def test_initialize_server_failure(self, mock_stdio_client, mock_params, mock_session):
        """Test server initialization failure."""
        
        # Make stdio_client raise an exception  
        def mock_stdio_func(*args, **kwargs):
            raise Exception("Connection failed")
        mock_stdio_client.side_effect = mock_stdio_func
        
        config = MCPServerConfig(
            name="test-server-1",
            command="python",
            args=["server1.py"],
            env={"VAR1": "value1"},
            type="stdio"
        )
        
        async def _test():
            connection = ServerConnection(config)
            with self.assertRaises(Exception):
                await connection.connect()
            
            # Verify connection failed
            self.assertFalse(connection.is_connected)
        
        self.run_async(_test)
    
    def test_initialize_all_servers_no_mcp_sdk(self):
        """Test server initialization when MCP SDK is not available."""
        manager = MCPClientManager(str(self.config_file))
        
        # Simulate MCP SDK not available
        async def _test():
            with patch('dromedary.mcp.client.stdio_client', None):
                with patch('dromedary.mcp.client.ClientSession', None):
                    # Should gracefully handle missing SDK and return empty list
                    successful_servers = await manager.initialize_from_config()
                    self.assertEqual(successful_servers, [])
                    self.assertEqual(len(manager._connections), 0)
        
        self.run_async(_test)
    
    def test_get_all_tools(self):
        """Test getting all tools."""
        
        manager = MCPClientManager(str(self.config_file))
        
        # Create mock connections with tools
        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool2 = Mock() 
        mock_tool2.name = "tool2"
        
        config1 = MCPServerConfig(name="server1", command="test", args=[], env={})
        config2 = MCPServerConfig(name="server2", command="test", args=[], env={})
        
        connection1 = ServerConnection(config1)
        connection1._tools = {"tool1": mock_tool1}
        connection1._session = Mock()  # Mock session to indicate connected state
        connection1._exit_stack = Mock()
        
        connection2 = ServerConnection(config2)
        connection2._tools = {"tool2": mock_tool2}
        connection2._session = Mock()  # Mock session to indicate connected state
        connection2._exit_stack = Mock()
        
        manager._connections = {"server1": connection1, "server2": connection2}
        
        tools = manager.get_all_tools()
        
        self.assertEqual(len(tools), 2)
        self.assertIn("tool1", tools)
        self.assertIn("tool2", tools)
        self.assertIs(tools["tool1"], mock_tool1)
        self.assertIs(tools["tool2"], mock_tool2)
    
    def test_get_tool(self):
        """Test getting specific tool."""
        
        manager = MCPClientManager(str(self.config_file))
        
        mock_tool = Mock()
        
        config = MCPServerConfig(name="test-server", command="test", args=[], env={})
        connection = ServerConnection(config)
        connection._tools = {"target_tool": mock_tool}
        connection._session = Mock()  # Mock session to indicate connected state
        connection._exit_stack = Mock()
        
        manager._connections = {"test-server": connection}
        manager._tool_to_server_mapping = {"target_tool": "test-server"}
        
        # Test existing tool
        result = manager.get_tool("target_tool")
        self.assertIs(result, mock_tool)
        
        # Test non-existing tool
        result = manager.get_tool("nonexistent_tool")
        self.assertIsNone(result)
    
    def test_call_tool_success(self):
        """Test successful tool call."""
        
        manager = MCPClientManager(str(self.config_file))
        
        # Setup mock connection
        mock_tool = Mock()
        config = MCPServerConfig(name="test-server", command="test", args=[], env={})
        connection = ServerConnection(config)
        connection._tools = {"test_tool": mock_tool}
        connection._session = Mock()  # Mock session to indicate connected state
        connection._exit_stack = Mock()
        connection.call_tool = AsyncMock(return_value="tool_result")
        
        manager._connections = {"test-server": connection}
        manager._tool_to_server_mapping = {"test_tool": "test-server"}
        
        async def _test():
            result = await manager.call_tool("test_tool", {"arg1": "value1"})
            self.assertEqual(result, "tool_result")
            connection.call_tool.assert_called_once_with("test_tool", {"arg1": "value1"})
        
        self.run_async(_test)
    
    def test_call_tool_with_server_prefix(self):
        """Test tool call with server prefix."""
        
        manager = MCPClientManager(str(self.config_file))
        
        mock_tool = Mock()
        config = MCPServerConfig(name="test-server", command="test", args=[], env={})
        connection = ServerConnection(config)
        connection._tools = {"prefixed_tool": mock_tool}
        connection._session = Mock()  # Mock session to indicate connected state
        connection._exit_stack = Mock()
        connection.call_tool = AsyncMock(return_value="prefixed_result")
        
        manager._connections = {"test-server": connection}
        manager._tool_to_server_mapping = {"test-server.prefixed_tool": "test-server"}
        
        async def _test():
            result = await manager.call_tool("test-server.prefixed_tool", {"arg1": "value1"})
            self.assertEqual(result, "prefixed_result")
            # Verify the server prefix was stripped from the tool name
            connection.call_tool.assert_called_once_with("prefixed_tool", {"arg1": "value1"})
        
        self.run_async(_test)
    
    def test_call_tool_not_found(self):
        """Test tool call with unknown tool."""
        manager = MCPClientManager(str(self.config_file))
        
        async def _test():
            with self.assertRaises(ValueError) as cm:
                await manager.call_tool("unknown_tool", {})
            self.assertIn("Tool 'unknown_tool' not found", str(cm.exception))
        
        self.run_async(_test)
    
    def test_call_tool_no_session(self):
        """Test tool call when server session is not available."""
        manager = MCPClientManager(str(self.config_file))
        
        manager._tool_to_server_mapping["test_tool"] = "test-server"
        # Don't add connection to manager._connections
        
        async def _test():
            with self.assertRaises(RuntimeError) as cm:
                await manager.call_tool("test_tool", {})
            self.assertIn("No active connection for server 'test-server'", str(cm.exception))
        
        self.run_async(_test)
    
    def test_call_tool_session_error(self):
        """Test tool call when session raises an error."""
        
        manager = MCPClientManager(str(self.config_file))
        
        mock_tool = Mock()
        config = MCPServerConfig(name="test-server", command="test", args=[], env={})
        connection = ServerConnection(config)
        connection._tools = {"test_tool": mock_tool}
        connection._session = Mock()  # Mock session to indicate connected state
        connection._exit_stack = Mock()
        connection.call_tool = AsyncMock(side_effect=Exception("Connection error"))
        
        manager._connections = {"test-server": connection}
        manager._tool_to_server_mapping = {"test_tool": "test-server"}
        
        async def _test():
            with self.assertRaises(Exception):
                await manager.call_tool("test_tool", {})
        
        self.run_async(_test)
    
    def test_is_connected(self):
        """Test server connection status."""
        
        manager = MCPClientManager(str(self.config_file))
        
        # Test not connected
        self.assertFalse(manager.is_connected("test-server"))
        
        # Add mock connection
        config = MCPServerConfig(name="test-server", command="test", args=[], env={})
        connection = ServerConnection(config)
        connection._session = Mock()  # Mock session to indicate connected state
        connection._exit_stack = Mock()
        manager._connections = {"test-server": connection}
        
        # Test connected
        self.assertTrue(manager.is_connected("test-server"))
    
    def test_get_connected_servers(self):
        """Test getting list of connected servers."""
        
        manager = MCPClientManager(str(self.config_file))
        
        # Initially no servers connected
        self.assertEqual(manager.get_connected_servers(), [])
        
        # Add mock connections
        config1 = MCPServerConfig(name="server1", command="test", args=[], env={})
        config2 = MCPServerConfig(name="server2", command="test", args=[], env={})
        
        connection1 = ServerConnection(config1)
        connection1._session = Mock()  # Mock session to indicate connected state
        connection1._exit_stack = Mock()
        connection2 = ServerConnection(config2)
        connection2._session = Mock()  # Mock session to indicate connected state
        connection2._exit_stack = Mock()
        
        manager._connections = {"server1": connection1, "server2": connection2}
        
        connected = manager.get_connected_servers()
        self.assertEqual(set(connected), {"server1", "server2"})
    
    def test_shutdown(self):
        """Test shutdown process."""
        
        manager = MCPClientManager(str(self.config_file))
        
        # Add mock connections
        config1 = MCPServerConfig(name="server1", command="test", args=[], env={})
        config2 = MCPServerConfig(name="server2", command="test", args=[], env={})
        
        connection1 = ServerConnection(config1)
        connection1._session = Mock()  # Mock session to indicate connected state
        connection1._exit_stack = Mock()
        connection1.disconnect = AsyncMock()
        
        connection2 = ServerConnection(config2)
        connection2._session = Mock()  # Mock session to indicate connected state
        connection2._exit_stack = Mock()
        connection2.disconnect = AsyncMock()
        
        manager._connections = {"server1": connection1, "server2": connection2}
        manager._tool_to_server_mapping = {"tool1": "server1"}
        
        async def _test():
            await manager.shutdown()
            
            # Verify connections were disconnected
            connection1.disconnect.assert_called_once()
            connection2.disconnect.assert_called_once()
            
            # Verify cleanup
            self.assertEqual(len(manager._connections), 0)
            self.assertEqual(len(manager._tool_to_server_mapping), 0)
        
        self.run_async(_test)
    
    def test_shutdown_with_session_errors(self):
        """Test shutdown when some connections raise errors."""
        
        manager = MCPClientManager(str(self.config_file))
        
        # Add mock connections with one that raises an error
        config1 = MCPServerConfig(name="server1", command="test", args=[], env={})
        config2 = MCPServerConfig(name="server2", command="test", args=[], env={})
        
        connection1 = ServerConnection(config1)
        connection1._session = Mock()  # Mock session to indicate connected state
        connection1._exit_stack = Mock()
        connection1.disconnect = AsyncMock(side_effect=Exception("Shutdown error"))
        
        connection2 = ServerConnection(config2)
        connection2._session = Mock()  # Mock session to indicate connected state
        connection2._exit_stack = Mock()
        connection2.disconnect = AsyncMock()
        
        manager._connections = {"server1": connection1, "server2": connection2}
        
        async def _test():
            # Shutdown should complete even with errors
            await manager.shutdown()
            
            # Verify both connections were attempted to be shutdown
            connection1.disconnect.assert_called_once()
            connection2.disconnect.assert_called_once()
            
            # Verify cleanup still happened
            self.assertEqual(len(manager._connections), 0)
        
        self.run_async(_test)


class TestMCPClientManagerIntegration(AsyncTestCase):
    """Integration tests for MCP client manager."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "integration-config.json"
        
        # Create integration test configuration
        self.integration_config = {
            "mcpServers": {
                "mock-server": {
                    "type": "stdio",
                    "command": "echo",
                    "args": ["mock"],
                    "env": {}
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(self.integration_config, f)
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        if self.config_file.exists():
            self.config_file.unlink()
        os.rmdir(self.temp_dir)
    
    @patch('dromedary.mcp.client.ClientSession')
    @patch('dromedary.mcp.client.StdioServerParameters')
    @patch('dromedary.mcp.client.stdio_client')
    def test_full_lifecycle(self, mock_stdio_client, mock_params, mock_session):
        """Test full server lifecycle: initialize, use, shutdown."""
        # Setup comprehensive mocks
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        def mock_stdio_func(*args, **kwargs):
            return mock_context
        mock_stdio_client.side_effect = mock_stdio_func
        
        mock_session_instance = AsyncMock()
        mock_session_instance.initialize = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        
        # Mock tools with realistic structure
        mock_tool = Mock()
        mock_tool.name = "test_function"
        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool])
        mock_session_instance.call_tool = AsyncMock(return_value="function_result")
        
        mock_session.return_value = mock_session_instance
        
        manager = MCPClientManager(str(self.config_file))
        
        async def _test():
            # Initialize servers
            successful_servers = await manager.initialize_from_config()
            self.assertEqual(successful_servers, ["mock-server"])
            
            # Verify server is connected
            self.assertTrue(manager.is_connected("mock-server"))
            self.assertEqual(manager.get_connected_servers(), ["mock-server"])
            
            # Verify tools are available
            tools = manager.get_all_tools()
            self.assertIn("test_function", tools)
            # Verify prefixed tool can be accessed (but not in tools dict)
            self.assertIsNotNone(manager.get_tool("mock-server.test_function"))
            
            # Test tool calling
            result = await manager.call_tool("test_function", {"param": "value"})
            self.assertEqual(result, "function_result")
            
            # Test shutdown
            await manager.shutdown()
            self.assertFalse(manager.is_connected("mock-server"))
            self.assertEqual(len(manager.get_all_tools()), 0)
        
        self.run_async(_test)


if __name__ == "__main__":
    # Run async tests
    def run_async_test(test_func):
        """Helper to run async test functions."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_func())
        finally:
            loop.close()
    
    unittest.main() 