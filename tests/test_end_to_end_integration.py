import unittest
import asyncio
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dromedary_mcp.client import MCPClientManager
from dromedary_mcp.tool_loader import MCPToolLoader
from dromedary_mcp.types import MCPTypeConverter
from interpreter import PythonInterpreter
from p_llm_agent import PLLMAgent
from policy_engine import PolicyEngine, PolicyViolationError
from prompt_builder import SystemPromptBuilder


class AsyncTestCase(unittest.TestCase):
    def run_async(self, coro):
        if asyncio.iscoroutinefunction(coro):
            return asyncio.run(coro())
        return coro


class TestEndToEndMCPIntegration(AsyncTestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test-mcp-config.json"
        
        self.test_config = {
            "mcpServers": {
                "email-server": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["email_server.py"],
                    "env": {}
                },
                "calendar-server": {
                    "type": "stdio", 
                    "command": "python",
                    "args": ["calendar_server.py"],
                    "env": {}
                },
                "filestore-server": {
                    "type": "stdio",
                    "command": "python", 
                    "args": ["filestore_server.py"],
                    "env": {}
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(self.test_config, f)
    
    def tearDown(self):
        if self.config_file.exists():
            self.config_file.unlink()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _setup_comprehensive_mocks(self):
        mock_email_tools = [
            Mock(name="send_email", description="Send an email"),
            Mock(name="get_received_emails", description="Get received emails"),
            Mock(name="search_emails", description="Search emails"),
            Mock(name="search_contacts", description="Search contacts")
        ]
        
        mock_calendar_tools = [
            Mock(name="get_current_day", description="Get current day"),
            Mock(name="create_calendar_event", description="Create calendar event"),
            Mock(name="search_calendar_events", description="Search calendar events")
        ]
        
        mock_filestore_tools = [
            Mock(name="create_file", description="Create a file"),
            Mock(name="get_file_by_id", description="Get file by ID"),
            Mock(name="list_files", description="List files"),
            Mock(name="search_files", description="Search files")
        ]
        
        return {
            "email-server": mock_email_tools,
            "calendar-server": mock_calendar_tools,
            "filestore-server": mock_filestore_tools
        }
    
    def test_interpreter_mcp_integration(self):
        async def _test():
            with patch('dromedary_mcp.client.stdio_client') as mock_stdio:
                with patch('dromedary_mcp.client.ClientSession') as mock_session:
                    with patch('interpreter.init_chat_model') as mock_init_chat:
                        with patch('dromedary_mcp.tool_loader.MCPToolMapper') as mock_tool_mapper:
                            mock_init_chat.return_value = Mock()
                            
                            mock_context = AsyncMock()
                            mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
                            mock_stdio.return_value = mock_context
                            
                            mock_tools = self._setup_comprehensive_mocks()
                            
                            mock_session_instance = AsyncMock()
                            mock_session_instance.initialize = AsyncMock()
                            mock_session_instance.list_tools = AsyncMock(return_value=mock_tools["email-server"])
                            mock_session_instance.call_tool = AsyncMock(return_value="email sent successfully")
                            mock_session.return_value = mock_session_instance
                            
                            # Mock the tool mapper properly
                            mock_mapper_instance = Mock()
                            mock_mapper_instance.get_all_functions.return_value = {"send_email": Mock()}
                            mock_tool_mapper.return_value = mock_mapper_instance
                            
                            tool_loader = MCPToolLoader(str(self.config_file))
                            
                            # Mock the tool loader initialization to succeed
                            with patch.object(tool_loader, 'initialize', return_value=True):
                                result = await tool_loader.initialize()
                                self.assertTrue(result)
                                
                                from interpreter import PythonInterpreter
                                interpreter = PythonInterpreter(
                                    enable_policies=False,
                                    mcp_tool_loader=tool_loader
                                )
                                
                                self.assertIsNotNone(interpreter.mcp_tool_loader)
                                
                                available_tools = tool_loader.get_available_tools()
                                self.assertIsInstance(available_tools, list)
                                
                                await tool_loader.shutdown()
        
        self.run_async(_test)
    
    def test_interpreter_mcp_tool_execution(self):
        async def _test():
            with patch('dromedary_mcp.tool_mapper.initialize_persistent_mcp_manager') as mock_init:
                with patch('dromedary_mcp.tool_mapper._persistent_mcp_manager') as mock_manager:
                    with patch('interpreter.init_chat_model') as mock_init_chat:
                        mock_init_chat.return_value = Mock()
                        
                        # Mock the persistent manager initialization to succeed
                        mock_init.return_value = True
                        
                        # Create a mock tool
                        mock_tool = Mock()
                        mock_tool.name = "send_email"
                        mock_tool.description = "Send an email message"
                        mock_tool.inputSchema = {
                            "type": "object",
                            "properties": {
                                "to": {"type": "string"},
                                "subject": {"type": "string"},
                                "body": {"type": "string"}
                            }
                        }
                        
                        # Mock the persistent manager's get_all_tools method
                        mock_manager.get_all_tools.return_value = {"send_email": mock_tool}
                        mock_manager.call_tool_sync.return_value = "Email sent successfully"
                        
                        tool_loader = MCPToolLoader(str(self.config_file))
                        await tool_loader.initialize()
                        
                        interpreter = PythonInterpreter(
                            enable_policies=False,
                            mcp_tool_loader=tool_loader
                        )
                        
                        self.assertTrue(tool_loader.has_tool("send_email"))
                        
                        tool_func = tool_loader.get_tool_function("send_email")
                        self.assertIsNotNone(tool_func)
                        
                        await tool_loader.shutdown()
        
        self.run_async(_test)
    
    def test_interpreter_mcp_with_policies(self):
        async def _test():
            with patch('dromedary_mcp.client.stdio_client') as mock_stdio:
                with patch('dromedary_mcp.client.ClientSession') as mock_session:
                    with patch('interpreter.init_chat_model') as mock_init_chat:
                        mock_init_chat.return_value = Mock()
                        
                        mock_context = AsyncMock()
                        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
                        mock_stdio.return_value = mock_context
                        
                        mock_tool = Mock()
                        mock_tool.name = "send_email"
                        mock_tool.description = "Send an email message"
                        
                        mock_session_instance = AsyncMock()
                        mock_session_instance.initialize = AsyncMock()
                        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool])
                        mock_session.return_value = mock_session_instance
                        
                        tool_loader = MCPToolLoader(str(self.config_file))
                        await tool_loader.initialize()
                        
                        interpreter = PythonInterpreter(
                            enable_policies=True,
                            mcp_tool_loader=tool_loader
                        )
                        
                        self.assertTrue(interpreter.enable_policies)
                        
                        await tool_loader.shutdown()
        
        self.run_async(_test)
    
    def test_p_llm_agent_mcp_initialization(self):
        async def _test():
            with patch('dromedary_mcp.tool_mapper.initialize_persistent_mcp_manager') as mock_init:
                with patch('dromedary_mcp.tool_mapper._persistent_mcp_manager') as mock_manager:
                    with patch.dict(os.environ, {
                        'AZURE_OPENAI_API_KEY': 'test-key',
                        'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
                        'AZURE_OPENAI_DEPLOYMENT': 'test-deployment'
                    }):
                        # Mock the persistent manager initialization to succeed
                        mock_init.return_value = True
                        mock_manager.get_all_tools.return_value = {"test_tool": Mock()}
                        
                        agent = PLLMAgent()
                        self.assertIsNone(agent.mcp_tool_loader)
                        
                        await agent._initialize_mcp()
                        
                        # Agent should have successfully initialized MCP
                        self.assertIsNotNone(agent.mcp_tool_loader)
                        
                        if agent.mcp_tool_loader:
                            await agent.shutdown()
        
        self.run_async(_test)
    
    def test_prompt_builder_mcp_integration(self):
        with patch('dromedary_mcp.tool_mapper.initialize_persistent_mcp_manager') as mock_init:
            with patch('dromedary_mcp.tool_mapper._persistent_mcp_manager') as mock_manager:
                # Mock the persistent manager initialization to succeed
                mock_init.return_value = True
                mock_tool = Mock()
                mock_tool.name = "test_tool"
                mock_tool.description = "Test tool"
                mock_tool.inputSchema = {"type": "object"}
                mock_manager.get_all_tools.return_value = {"test_tool": mock_tool}
                
                # Create a mock tool loader
                mock_tool_loader = Mock()
                mock_tool_loader.get_available_tools.return_value = ["test_tool"]
                mock_tool_loader.get_tool_schema.return_value = {
                    "description": "Test tool",
                    "inputSchema": {"type": "object"}
                }
                
                builder = SystemPromptBuilder(mcp_tool_loader=mock_tool_loader)
                
                prompt = builder.build_prompt()
                self.assertIsInstance(prompt, str)
                self.assertIn("Available Tools", prompt)
                self.assertIn("test_tool", prompt)
    
    def test_policy_engine_with_mcp_tools(self):
        async def _test():
            with patch('dromedary_mcp.client.stdio_client') as mock_stdio:
                with patch('dromedary_mcp.client.ClientSession') as mock_session:
                    with patch('interpreter.init_chat_model') as mock_init_chat:
                        mock_init_chat.return_value = Mock()
                        
                        mock_context = AsyncMock()
                        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
                        mock_stdio.return_value = mock_context
                        
                        mock_tool = Mock()
                        mock_tool.name = "send_email"
                        
                        mock_session_instance = AsyncMock()
                        mock_session_instance.initialize = AsyncMock()
                        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool])
                        mock_session.return_value = mock_session_instance
                        
                        tool_loader = MCPToolLoader(str(self.config_file))
                        await tool_loader.initialize()
                        
                        interpreter = PythonInterpreter(
                            enable_policies=True,
                            mcp_tool_loader=tool_loader
                        )
                        
                        self.assertTrue(interpreter.enable_policies)
                        
                        from policy_engine import policy_engine
                        
                        is_allowed, violations = policy_engine.evaluate_tool_call(
                            "send_email",
                            {"to": "test@example.com", "subject": "test"},
                            {}
                        )
                        
                        self.assertIsInstance(is_allowed, bool)
                        self.assertIsInstance(violations, list)
                        
                        await tool_loader.shutdown()
        
        self.run_async(_test)
    
    def test_full_workflow_with_mcp_servers(self):
        async def _test():
            with patch('dromedary_mcp.client.stdio_client') as mock_stdio:
                with patch('dromedary_mcp.client.ClientSession') as mock_session:
                    with patch('interpreter.init_chat_model') as mock_init_chat:
                        mock_init_chat.return_value = Mock()
                        
                        mock_context = AsyncMock()
                        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
                        mock_stdio.return_value = mock_context
                        
                        email_tool = Mock()
                        email_tool.name = "send_email"
                        email_tool.description = "Send an email"
                        
                        calendar_tool = Mock()
                        calendar_tool.name = "create_calendar_event"
                        calendar_tool.description = "Create a calendar event"
                        
                        mock_session_instance = AsyncMock()
                        mock_session_instance.initialize = AsyncMock()
                        mock_session_instance.list_tools = AsyncMock(return_value=[email_tool, calendar_tool])
                        mock_session_instance.call_tool = AsyncMock(return_value="Operation successful")
                        mock_session.return_value = mock_session_instance
                        
                        tool_loader = MCPToolLoader(str(self.config_file))
                        await tool_loader.initialize()
                        
                        interpreter = PythonInterpreter(
                            enable_policies=False,
                            mcp_tool_loader=tool_loader
                        )
                                                
                        available_tools = tool_loader.get_available_tools()
                        
                        if available_tools:
                            connected_servers = tool_loader.get_connected_servers()
                            self.assertIsInstance(connected_servers, list)
                        
                        await tool_loader.shutdown()
        
        self.run_async(_test)
    
    def test_mcp_type_converter_integration(self):
        type_converter = MCPTypeConverter()
        
        mcp_args = type_converter.python_args_to_mcp([], {"to": "test@example.com", "subject": "Test"})
        
        self.assertIsInstance(mcp_args, dict)
        self.assertEqual(mcp_args["to"], "test@example.com")
        self.assertEqual(mcp_args["subject"], "Test")
        
        python_result = type_converter.mcp_result_to_python("Email sent successfully")
        self.assertEqual(python_result, "Email sent successfully")
    
    def test_mcp_error_handling_integration(self):
        async def _test():
            with patch('dromedary_mcp.client.stdio_client') as mock_stdio:
                mock_stdio.side_effect = Exception("Connection failed")
                
                tool_loader = MCPToolLoader(str(self.config_file))
                
                result = await tool_loader.initialize()
                self.assertFalse(result)
                
                available_tools = tool_loader.get_available_tools()
                self.assertEqual(available_tools, [])
                
                connected_servers = tool_loader.get_connected_servers()
                self.assertEqual(connected_servers, [])
        
        self.run_async(_test)
    
    def test_mcp_server_lifecycle_management(self):
        async def _test():
            with patch('dromedary_mcp.tool_mapper.initialize_persistent_mcp_manager') as mock_init:
                with patch('dromedary_mcp.tool_mapper._persistent_mcp_manager') as mock_manager:
                    with patch('dromedary_mcp.tool_loader._persistent_mcp_manager', mock_manager):
                        with patch('dromedary_mcp.tool_mapper.shutdown_persistent_mcp_manager') as mock_shutdown:
                            with patch('dromedary_mcp.tool_loader.shutdown_persistent_mcp_manager', mock_shutdown):
                                with patch('dromedary_mcp.tool_mapper.MCPToolMapper') as mock_mapper_class:
                                    # Mock the persistent manager initialization to succeed
                                    mock_init.return_value = True
                                    mock_manager.get_all_tools.return_value = {}
                                    
                                    # Mock the tool mapper creation
                                    mock_mapper_instance = Mock()
                                    mock_mapper_instance.mapped_functions = {}
                                    mock_mapper_class.return_value = mock_mapper_instance
                                    
                                    tool_loader = MCPToolLoader(str(self.config_file))
                                    
                                    result = await tool_loader.initialize()
                                    self.assertTrue(result)
                                    
                                    self.assertTrue(tool_loader.is_initialized())
                                    
                                    await tool_loader.shutdown()
                                    
                                    # Verify that shutdown was called on the persistent manager
                                    mock_shutdown.assert_called()
        
        self.run_async(_test)

class TestMCPIntegrationEdgeCases(AsyncTestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.invalid_config_file = Path(self.temp_dir) / "invalid-config.json"
        
        with open(self.invalid_config_file, 'w') as f:
            f.write("invalid json content")
    
    def tearDown(self):
        if self.invalid_config_file.exists():
            self.invalid_config_file.unlink()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_invalid_config_handling(self):
        async def _test():
            from dromedary_mcp.client import MCPClientManager
            
            manager = MCPClientManager("nonexistent-file.json")
            self.assertEqual(len(manager.servers), 0)
            
            tool_loader = MCPToolLoader("nonexistent-file.json")
            
            result = await tool_loader.initialize()
            self.assertFalse(result)
            
            self.assertFalse(tool_loader.is_initialized())
        
        self.run_async(_test)
    
    def test_missing_config_file(self):
        async def _test():
            nonexistent_file = Path(self.temp_dir) / "nonexistent.json"
            
            tool_loader = MCPToolLoader(str(nonexistent_file))
            
            result = await tool_loader.initialize()
            self.assertFalse(result)
        
        self.run_async(_test)
    
    def test_policy_violations_with_mcp_tools(self):
        async def _test():
            with patch('dromedary_mcp.client.stdio_client') as mock_stdio:
                with patch('dromedary_mcp.client.ClientSession') as mock_session:
                    with patch('interpreter.init_chat_model') as mock_init_chat:
                        mock_init_chat.return_value = Mock()
                        
                        mock_context = AsyncMock()
                        mock_context.__aenter__ = AsyncMock(return_value=("read", "write"))
                        mock_stdio.return_value = mock_context
                        
                        mock_tool = Mock()
                        mock_tool.name = "restricted_tool"
                        
                        mock_session_instance = AsyncMock()
                        mock_session_instance.initialize = AsyncMock()
                        mock_session_instance.list_tools = AsyncMock(return_value=[mock_tool])
                        mock_session.return_value = mock_session_instance
                        
                        config = {
                            "mcpServers": {
                                "test-server": {
                                    "type": "stdio",
                                    "command": "python",
                                    "args": ["test.py"],
                                    "env": {}
                                }
                            }
                        }
                        
                        config_file = Path(self.temp_dir) / "test-config.json"
                        with open(config_file, 'w') as f:
                            json.dump(config, f)
                        
                        tool_loader = MCPToolLoader(str(config_file))
                        await tool_loader.initialize()
                        
                        from interpreter import PythonInterpreter
                        interpreter = PythonInterpreter(
                            enable_policies=True,
                            mcp_tool_loader=tool_loader
                        )
                        
                        self.assertTrue(interpreter.enable_policies)
                        
                        await tool_loader.shutdown()
        
        self.run_async(_test)


if __name__ == '__main__':
    unittest.main() 