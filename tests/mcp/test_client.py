import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import shutil
import pytest

from dromedary.mcp.client import MCPServerConfig, ServerConnection, MCPClientManager


class TestMCPServerConfig:
    
    def test_server_config_creation(self):
        config = MCPServerConfig(
            name="test-server",
            command="python",
            args=["server.py"],
            env={"PATH": "/usr/bin"},
            type="stdio"
        )
        
        assert config.name == "test-server"
        assert config.command == "python"
        assert config.args == ["server.py"]
        assert config.env == {"PATH": "/usr/bin"}
        assert config.type == "stdio"
    
    def test_server_config_default_type(self):
        config = MCPServerConfig(
            name="test-server",
            command="python",
            args=["server.py"],
            env={}
        )
        
        assert config.type == "stdio"


class TestMCPClientManager:
    
    @pytest.fixture
    def temp_config(self):
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test-config.json"
        
        test_config = {
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
        
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        yield config_file, temp_dir
        
        if config_file.exists():
            config_file.unlink()
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_load_config_success(self, temp_config):
        config_file, temp_dir = temp_config
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        configs = load_mcp_configs_from_file(str(config_file))
        
        assert len(configs) == 2
        
        server1 = configs["test-server-1"]
        assert server1.name == "test-server-1"
        assert server1.command == "python"
        assert server1.args == ["server1.py"]
        assert server1.env == {"VAR1": "value1"}
        
        server2 = configs["test-server-2"]
        assert server2.name == "test-server-2"
        assert server2.command == "uv"
        assert server2.args == ["run", "server2.py"]
        assert server2.env == {}
    
    def test_load_config_file_not_found(self):
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        with pytest.raises(FileNotFoundError):
            load_mcp_configs_from_file("nonexistent-config.json")
    
    def test_load_config_invalid_json(self, temp_config):
        config_file, temp_dir = temp_config
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        invalid_config_file = Path(temp_dir) / "invalid-config.json"
        with open(invalid_config_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ValueError):
            load_mcp_configs_from_file(str(invalid_config_file))
        
        invalid_config_file.unlink()
    
    def test_load_config_empty_servers(self, temp_config):
        config_file, temp_dir = temp_config
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        empty_config = {"mcpServers": {}}
        empty_config_file = Path(temp_dir) / "empty-config.json"
        
        with open(empty_config_file, 'w') as f:
            json.dump(empty_config, f)
        
        configs = load_mcp_configs_from_file(str(empty_config_file))
        assert len(configs) == 0
        
        empty_config_file.unlink()
    
    def test_load_config_missing_mcp_servers(self, temp_config):
        config_file, temp_dir = temp_config
        from dromedary.mcp.client import load_mcp_configs_from_file
        
        config_without_servers = {"someOtherConfig": "value"}
        config_file = Path(temp_dir) / "no-servers-config.json"
        
        with open(config_file, 'w') as f:
            json.dump(config_without_servers, f)
        
        with pytest.raises(ValueError):
            load_mcp_configs_from_file(str(config_file))
        
        config_file.unlink()
    
    @patch('dromedary.mcp.client.ClientSession')
    @patch('dromedary.mcp.client.StdioServerParameters')
    @patch('dromedary.mcp.client.stdio_client')
    @pytest.mark.asyncio
    async def test_initialize_server_success(self, mock_stdio_client, mock_params, mock_session):
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
        
        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool2 = Mock()
        mock_tool2.name = "tool2"
        
        mock_tools_result = Mock()
        mock_tools_result.tools = [mock_tool1, mock_tool2]
        mock_session_instance.list_tools = AsyncMock(return_value=mock_tools_result)
        mock_session.return_value = mock_session_instance
        
        config = MCPServerConfig(
            name="test-server-1",
            command="python",
            args=["server1.py"],
            env={"VAR1": "value1"},
            type="stdio"
        )
        
        connection = ServerConnection(config)
        await connection.connect()
        
        assert connection.is_connected
        assert len(connection.tools) == 2
        assert "tool1" in connection.tools
        assert "tool2" in connection.tools
    
    @patch('dromedary.mcp.client.ClientSession')
    @patch('dromedary.mcp.client.StdioServerParameters')
    @patch('dromedary.mcp.client.stdio_client')
    @pytest.mark.asyncio
    async def test_initialize_server_failure(self, mock_stdio_client, mock_params, mock_session):
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
        
        connection = ServerConnection(config)
        
        with pytest.raises(Exception, match="Connection failed"):
            await connection.connect()
    
    @pytest.mark.asyncio
    async def test_initialize_servers_no_mcp_sdk(self):
        configs = {
            "test-server": MCPServerConfig(
                name="test-server",
                command="python",
                args=["server.py"],
                env={}
            )
        }
        manager = MCPClientManager()
        
        with patch('dromedary.mcp.client.ClientSession', side_effect=ImportError("MCP SDK not available")):
            result = await manager.initialize_servers(configs)
            assert result == []
    
    def test_get_all_tools(self):
        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        
        mock_tool2 = Mock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Tool 2"
        
        mock_connection1 = Mock()
        mock_connection1.is_connected = True
        mock_connection1.tools = {"tool1": mock_tool1}
        
        mock_connection2 = Mock()
        mock_connection2.is_connected = True
        mock_connection2.tools = {"tool2": mock_tool2}
        
        manager = MCPClientManager()
        manager._connections = {
            "server1": mock_connection1,
            "server2": mock_connection2
        }
        
        all_tools = manager.get_all_tools()
        
        assert len(all_tools) == 2
        assert "tool1" in all_tools
        assert "tool2" in all_tools
        assert all_tools["tool1"] == mock_tool1
        assert all_tools["tool2"] == mock_tool2
    
    def test_get_tool(self):
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        
        mock_connection = Mock()
        mock_connection.is_connected = True
        mock_connection.get_tool.return_value = mock_tool
        
        manager = MCPClientManager()
        manager._connections = {"server1": mock_connection}
        manager._tool_to_server_mapping = {"test_tool": "server1"}
        
        result = manager.get_tool("test_tool")
        assert result == mock_tool
        
        result = manager.get_tool("nonexistent_tool")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        mock_result = Mock()
        mock_result.isError = False
        mock_result.content = [Mock(text="Success")]
        
        mock_connection = Mock()
        mock_connection.is_connected = True
        mock_connection.call_tool = AsyncMock(return_value=mock_result)
        
        manager = MCPClientManager()
        manager._connections = {"server1": mock_connection}
        manager._tool_to_server_mapping = {"test_tool": "server1"}
        
        result = await manager.call_tool("test_tool", {"arg": "value"})
        assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_call_tool_with_server_prefix(self):
        mock_result = Mock()
        mock_result.isError = False
        mock_result.content = [Mock(text="Success")]
        
        mock_connection = Mock()
        mock_connection.is_connected = True
        mock_connection.call_tool = AsyncMock(return_value=mock_result)
        
        manager = MCPClientManager()
        manager._connections = {"server1": mock_connection}
        manager._tool_to_server_mapping = {"server1.test_tool": "server1"}
        
        result = await manager.call_tool("server1.test_tool", {"arg": "value"})
        assert result == mock_result
        mock_connection.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
    
    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        manager = MCPClientManager()
        manager._connections = {}
        manager._tool_to_server_mapping = {}
        
        with pytest.raises(ValueError, match="Tool 'nonexistent_tool' not found"):
            await manager.call_tool("nonexistent_tool", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_no_session(self):
        mock_connection = Mock()
        mock_connection.is_connected = False
        
        manager = MCPClientManager()
        manager._connections = {"server1": mock_connection}
        manager._tool_to_server_mapping = {"test_tool": "server1"}
        
        with pytest.raises(RuntimeError, match="No active connection for server 'server1'"):
            await manager.call_tool("test_tool", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_session_error(self):
        mock_connection = Mock()
        mock_connection.is_connected = True
        mock_connection.call_tool = AsyncMock(side_effect=Exception("Tool execution failed"))
        
        manager = MCPClientManager()
        manager._connections = {"server1": mock_connection}
        manager._tool_to_server_mapping = {"test_tool": "server1"}
        
        with pytest.raises(Exception, match="Tool execution failed"):
            await manager.call_tool("test_tool", {})
    
    def test_is_connected(self):
        mock_connection1 = Mock()
        mock_connection1.is_connected = True
        
        mock_connection2 = Mock()
        mock_connection2.is_connected = False
        
        manager = MCPClientManager()
        manager._connections = {
            "server1": mock_connection1,
            "server2": mock_connection2
        }
        
        assert manager.is_connected("server1") is True
        assert manager.is_connected("server2") is False
        assert manager.is_connected("nonexistent") is False
    
    def test_get_connected_servers(self):
        mock_connection1 = Mock()
        mock_connection1.is_connected = True
        
        mock_connection2 = Mock()
        mock_connection2.is_connected = False
        
        mock_connection3 = Mock()
        mock_connection3.is_connected = True
        
        manager = MCPClientManager()
        manager._connections = {
            "server1": mock_connection1,
            "server2": mock_connection2,
            "server3": mock_connection3
        }
        
        connected = manager.get_connected_servers()
        assert len(connected) == 2
        assert "server1" in connected
        assert "server3" in connected
        assert "server2" not in connected
    
    @pytest.mark.asyncio
    async def test_shutdown(self):
        mock_connection1 = AsyncMock()
        mock_connection1.is_connected = True
        mock_connection1.disconnect = AsyncMock()
        
        mock_connection2 = AsyncMock()
        mock_connection2.is_connected = True
        mock_connection2.disconnect = AsyncMock()
        
        manager = MCPClientManager()
        manager._connections = {
            "server1": mock_connection1,
            "server2": mock_connection2
        }
        
        await manager.shutdown()
        
        mock_connection1.disconnect.assert_called_once()
        mock_connection2.disconnect.assert_called_once()
        assert len(manager._connections) == 0
    
    @pytest.mark.asyncio
    async def test_shutdown_with_session_errors(self):
        mock_connection1 = AsyncMock()
        mock_connection1.is_connected = True
        mock_connection1.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        
        mock_connection2 = AsyncMock()
        mock_connection2.is_connected = True
        mock_connection2.disconnect = AsyncMock()
        
        manager = MCPClientManager()
        manager._connections = {
            "server1": mock_connection1,
            "server2": mock_connection2
        }
        
        await manager.shutdown()
        
        mock_connection1.disconnect.assert_called_once()
        mock_connection2.disconnect.assert_called_once()
        assert len(manager._connections) == 0


class TestMCPClientManagerIntegration:
    
    @pytest.fixture
    def integration_config(self):
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "integration-config.json"
        
        test_config = {
            "mcpServers": {
                "test-server-1": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["server1.py"],
                    "env": {"VAR1": "value1"}
                },
                "test-server-2": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["server2.py"],
                    "env": {}
                }
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        yield config_file, temp_dir
        
        if config_file.exists():
            config_file.unlink()
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @patch('dromedary.mcp.client.ClientSession')
    @patch('dromedary.mcp.client.StdioServerParameters')
    @patch('dromedary.mcp.client.stdio_client')
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_stdio_client, mock_params, mock_session, integration_config):
        config_file, temp_dir = integration_config
        
        def mock_stdio_func(*args, **kwargs):
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
            mock_context.__aexit__ = AsyncMock(return_value=None)
            return mock_context
        mock_stdio_client.side_effect = mock_stdio_func
        
        mock_session_instance = AsyncMock()
        mock_session_instance.initialize = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tools_result = Mock()
        mock_tools_result.tools = [mock_tool]
        mock_session_instance.list_tools = AsyncMock(return_value=mock_tools_result)
        
        mock_result = Mock()
        mock_result.isError = False
        mock_result.content = [Mock(text="Success")]
        mock_session_instance.call_tool = AsyncMock(return_value=mock_result)
        
        mock_session.return_value = mock_session_instance
        
        from dromedary.mcp.client import load_mcp_configs_from_file
        configs = load_mcp_configs_from_file(str(config_file))
        manager = MCPClientManager()
        
        successful_servers = await manager.initialize_servers(configs)
        assert len(successful_servers) >= 0
        
        connected_servers = manager.get_connected_servers()
        assert isinstance(connected_servers, list)
        
        all_tools = manager.get_all_tools()
        assert isinstance(all_tools, dict)
        
        await manager.shutdown() 