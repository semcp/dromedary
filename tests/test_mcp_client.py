import unittest
import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import shutil

from dromedary_mcp.client import MCPClientManager, MCPServerConfig


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
        manager = MCPClientManager(str(self.config_file))
        
        self.assertEqual(len(manager.servers), 2)
        
        server1 = manager.servers["test-server-1"]
        self.assertEqual(server1.name, "test-server-1")
        self.assertEqual(server1.command, "python")
        self.assertEqual(server1.args, ["server1.py"])
        self.assertEqual(server1.env, {"VAR1": "value1"})
        
        server2 = manager.servers["test-server-2"]
        self.assertEqual(server2.name, "test-server-2")
        self.assertEqual(server2.command, "uv")
        self.assertEqual(server2.args, ["run", "server2.py"])
        self.assertEqual(server2.env, {})
    
    def test_load_config_file_not_found(self):
        """Test configuration loading with missing file."""
        manager = MCPClientManager("nonexistent-config.json")
        self.assertEqual(len(manager.servers), 0)
    
    def test_load_config_invalid_json(self):
        """Test configuration loading with invalid JSON."""
        invalid_config_file = Path(self.temp_dir) / "invalid-config.json"
        with open(invalid_config_file, 'w') as f:
            f.write("invalid json content")
        
        manager = MCPClientManager(str(invalid_config_file))
        self.assertEqual(len(manager.servers), 0)
        
        invalid_config_file.unlink()
    
    def test_load_config_empty_servers(self):
        """Test configuration loading with empty mcpServers."""
        empty_config = {"mcpServers": {}}
        empty_config_file = Path(self.temp_dir) / "empty-config.json"
        
        with open(empty_config_file, 'w') as f:
            json.dump(empty_config, f)
        
        manager = MCPClientManager(str(empty_config_file))
        self.assertEqual(len(manager.servers), 0)
        
        empty_config_file.unlink()
    
    def test_load_config_missing_mcp_servers(self):
        """Test configuration loading without mcpServers key."""
        config_without_servers = {"someOtherConfig": "value"}
        config_file = Path(self.temp_dir) / "no-servers-config.json"
        
        with open(config_file, 'w') as f:
            json.dump(config_without_servers, f)
        
        manager = MCPClientManager(str(config_file))
        self.assertEqual(len(manager.servers), 0)
        
        config_file.unlink()
    
    @patch('dromedary_mcp.client.ClientSession')
    @patch('dromedary_mcp.client.StdioServerParameters')
    @patch('dromedary_mcp.client.stdio_client')
    def test_initialize_server_success(self, mock_stdio_client, mock_params, mock_session):
        """Test successful server initialization."""
        # Setup mocks
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
        mock_stdio_client.return_value = mock_context
        
        mock_session_instance = AsyncMock()
        mock_session_instance.initialize = AsyncMock()
        
        # Mock tools
        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool2 = Mock()
        mock_tool2.name = "tool2"
        
        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])
        mock_session.return_value = mock_session_instance
        
        manager = MCPClientManager(str(self.config_file))
        
        # Test single server initialization
        async def _test():
            await manager._initialize_server("test-server-1")
        
        self.run_async(_test)
        
        # Verify session was created and initialized
        mock_session.assert_called_once()
        mock_session_instance.initialize.assert_called_once()
        mock_session_instance.list_tools.assert_called_once()
        
        # Verify tools were registered
        self.assertIn("test-server-1", manager.sessions)
        self.assertIn("tool1", manager.tools)
        self.assertIn("tool2", manager.tools)
        # Verify prefixed tools can be accessed via get_tool (but not stored in tools dict)
        self.assertIsNotNone(manager.get_tool("test-server-1.tool1"))
        self.assertIsNotNone(manager.get_tool("test-server-1.tool2"))
    
    @patch('dromedary_mcp.client.ClientSession')
    @patch('dromedary_mcp.client.StdioServerParameters')
    @patch('dromedary_mcp.client.stdio_client')
    def test_initialize_server_failure(self, mock_stdio_client, mock_params, mock_session):
        """Test server initialization failure."""
        # Make stdio_client raise an exception
        mock_stdio_client.side_effect = Exception("Connection failed")
        
        manager = MCPClientManager(str(self.config_file))
        
        async def _test():
            with self.assertRaises(Exception):
                await manager._initialize_server("test-server-1")
        
        self.run_async(_test)
        
        # Verify no session was registered
        self.assertNotIn("test-server-1", manager.sessions)
    
    def test_initialize_all_servers_no_mcp_sdk(self):
        """Test server initialization when MCP SDK is not available."""
        manager = MCPClientManager(str(self.config_file))
        
        # Simulate MCP SDK not available
        async def _test():
            with patch('dromedary_mcp.client.stdio_client', None):
                with patch('dromedary_mcp.client.ClientSession', None):
                    with self.assertRaises(RuntimeError):
                        await manager._initialize_server("test-server-1")
        
        self.run_async(_test)
    
    def test_get_all_tools(self):
        """Test getting all tools."""
        manager = MCPClientManager(str(self.config_file))
        
        # Add some mock tools
        mock_tool1 = Mock()
        mock_tool2 = Mock()
        manager.tools = {"tool1": mock_tool1, "tool2": mock_tool2}
        
        tools = manager.get_all_tools()
        
        self.assertEqual(len(tools), 2)
        self.assertIn("tool1", tools)
        self.assertIn("tool2", tools)
        self.assertIs(tools["tool1"], mock_tool1)
        self.assertIs(tools["tool2"], mock_tool2)
        
        # Verify it returns a copy (modifying returned dict doesn't affect original)
        tools["tool3"] = Mock()
        self.assertNotIn("tool3", manager.tools)
    
    def test_get_tool(self):
        """Test getting specific tool."""
        manager = MCPClientManager(str(self.config_file))
        
        mock_tool = Mock()
        manager.tools = {"target_tool": mock_tool}
        
        # Test existing tool
        result = manager.get_tool("target_tool")
        self.assertIs(result, mock_tool)
        
        # Test non-existing tool
        result = manager.get_tool("nonexistent_tool")
        self.assertIsNone(result)
    
    def test_call_tool_success(self):
        """Test successful tool call."""
        manager = MCPClientManager(str(self.config_file))
        
        # Setup mock session
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value="tool_result")
        
        manager.sessions["test-server"] = mock_session
        manager.server_tool_mapping["test_tool"] = "test-server"
        
        async def _test():
            result = await manager.call_tool("test_tool", {"arg1": "value1"})
            self.assertEqual(result, "tool_result")
            mock_session.call_tool.assert_called_once_with("test_tool", {"arg1": "value1"})
        
        self.run_async(_test)
    
    def test_call_tool_with_server_prefix(self):
        """Test tool call with server prefix."""
        manager = MCPClientManager(str(self.config_file))
        
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value="prefixed_result")
        
        manager.sessions["test-server"] = mock_session
        manager.server_tool_mapping["test-server.prefixed_tool"] = "test-server"
        
        async def _test():
            result = await manager.call_tool("test-server.prefixed_tool", {"arg1": "value1"})
            self.assertEqual(result, "prefixed_result")
            # Verify the server prefix was stripped from the tool name
            mock_session.call_tool.assert_called_once_with("prefixed_tool", {"arg1": "value1"})
        
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
        
        manager.server_tool_mapping["test_tool"] = "test-server"
        # Don't add session to manager.sessions
        
        async def _test():
            with self.assertRaises(RuntimeError) as cm:
                await manager.call_tool("test_tool", {})
            self.assertIn("No active session for server 'test-server'", str(cm.exception))
        
        self.run_async(_test)
    
    def test_call_tool_session_error(self):
        """Test tool call when session raises an error."""
        manager = MCPClientManager(str(self.config_file))
        
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(side_effect=Exception("Session error"))
        
        manager.sessions["test-server"] = mock_session
        manager.server_tool_mapping["test_tool"] = "test-server"
        
        async def _test():
            with self.assertRaises(Exception):
                await manager.call_tool("test_tool", {})
        
        self.run_async(_test)
    
    def test_is_connected(self):
        """Test server connection status."""
        manager = MCPClientManager(str(self.config_file))
        
        # Test not connected
        self.assertFalse(manager.is_connected("test-server"))
        
        # Add mock session
        manager.sessions["test-server"] = Mock()
        
        # Test connected
        self.assertTrue(manager.is_connected("test-server"))
    
    def test_get_connected_servers(self):
        """Test getting list of connected servers."""
        manager = MCPClientManager(str(self.config_file))
        
        # Initially no servers connected
        self.assertEqual(manager.get_connected_servers(), [])
        
        # Add mock sessions
        manager.sessions["server1"] = Mock()
        manager.sessions["server2"] = Mock()
        
        connected = manager.get_connected_servers()
        self.assertEqual(set(connected), {"server1", "server2"})
    
    def test_shutdown(self):
        """Test shutdown process."""
        manager = MCPClientManager(str(self.config_file))
        
        # Add mock sessions and exit stacks
        mock_session1 = AsyncMock()
        mock_session1.__aexit__ = AsyncMock()
        mock_session2 = AsyncMock()
        mock_session2.__aexit__ = AsyncMock()
        
        # Mock exit stacks
        mock_exit_stack1 = AsyncMock()
        mock_exit_stack1.aclose = AsyncMock()
        mock_exit_stack2 = AsyncMock()
        mock_exit_stack2.aclose = AsyncMock()
        
        manager.sessions["server1"] = mock_session1
        manager.sessions["server2"] = mock_session2
        manager.exit_stacks["server1"] = mock_exit_stack1
        manager.exit_stacks["server2"] = mock_exit_stack2
        manager.tools["tool1"] = Mock()
        manager.server_tool_mapping["tool1"] = "server1"
        
        async def _test():
            await manager.shutdown()
            
            # Verify exit stacks were closed and sessions' __aexit__ called
            mock_exit_stack1.aclose.assert_called_once()
            mock_exit_stack2.aclose.assert_called_once()
            mock_session1.__aexit__.assert_called_once()
            mock_session2.__aexit__.assert_called_once()
            
            # Verify cleanup
            self.assertEqual(len(manager.sessions), 0)
            self.assertEqual(len(manager.tools), 0)
            self.assertEqual(len(manager.server_tool_mapping), 0)
        
        self.run_async(_test)
    
    def test_shutdown_with_session_errors(self):
        """Test shutdown when some sessions raise errors."""
        manager = MCPClientManager(str(self.config_file))
        
        # Add mock sessions with one that raises an error
        mock_session1 = AsyncMock()
        mock_session1.__aexit__ = AsyncMock(side_effect=Exception("Shutdown error"))
        mock_session2 = AsyncMock()
        mock_session2.__aexit__ = AsyncMock()
        
        # Mock exit stacks
        mock_exit_stack1 = AsyncMock()
        mock_exit_stack1.aclose = AsyncMock()
        mock_exit_stack2 = AsyncMock()
        mock_exit_stack2.aclose = AsyncMock()
        
        manager.sessions["server1"] = mock_session1
        manager.sessions["server2"] = mock_session2
        manager.exit_stacks["server1"] = mock_exit_stack1
        manager.exit_stacks["server2"] = mock_exit_stack2
        
        async def _test():
            # Shutdown should complete even with errors
            await manager.shutdown()
            
            # Verify both sessions were attempted to be shutdown
            mock_exit_stack1.aclose.assert_called_once()
            mock_exit_stack2.aclose.assert_called_once()
            mock_session1.__aexit__.assert_called_once()
            mock_session2.__aexit__.assert_called_once()
            
            # Verify cleanup still happened
            self.assertEqual(len(manager.sessions), 0)
        
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
    
    @patch('dromedary_mcp.client.ClientSession')
    @patch('dromedary_mcp.client.StdioServerParameters')
    @patch('dromedary_mcp.client.stdio_client')
    def test_full_lifecycle(self, mock_stdio_client, mock_params, mock_session):
        """Test full server lifecycle: initialize, use, shutdown."""
        # Setup comprehensive mocks
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
        mock_stdio_client.return_value = mock_context
        
        mock_session_instance = AsyncMock()
        mock_session_instance.initialize = AsyncMock()
        mock_session_instance.__aexit__ = AsyncMock()
        
        # Mock tools with realistic structure
        mock_tool = Mock()
        mock_tool.name = "test_function"
        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool])
        mock_session_instance.call_tool = AsyncMock(return_value="function_result")
        
        mock_session.return_value = mock_session_instance
        
        manager = MCPClientManager(str(self.config_file))
        
        async def _test():
            # Initialize servers
            successful_servers = await manager.initialize_all_servers()
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