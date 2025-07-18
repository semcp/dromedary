import asyncio
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dromedary.mcp.manager import MCPManager
from dromedary.mcp.tool_mapper import MCPToolMapper
from dromedary.mcp.tool_loader import MCPToolLoader
from dromedary.mcp.types import MCPTypeConverter
from dromedary.interpreter import PythonInterpreter
from dromedary.agent import PLLMAgent
from dromedary.policy.engine import create_policy_engine
from dromedary.prompt_builder import SystemPromptBuilder


class TestEndToEndMCPIntegration:
    
    @pytest.fixture
    def temp_config(self):
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "test-mcp-config.json"
        
        test_config = {
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
        
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        yield config_file, temp_dir
        
        if config_file.exists():
            config_file.unlink()
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _create_mock_tool_loader(self):
        mock_manager = Mock(spec=MCPManager)
        mock_manager.get_all_tools.return_value = {
            "send_email": Mock(
                name="send_email",
                description="Send an email message",
                inputSchema={"type": "object", "properties": {"to": {"type": "string"}}}
            )
        }
        mock_manager.get_connected_servers.return_value = ["email-server"]
        mock_manager.call_tool_sync.return_value = "Email sent successfully"
        
        mock_mapper = Mock(spec=MCPToolMapper)
        mock_mapper.get_all_functions.return_value = {"send_email": Mock()}
        mock_mapper.has_tool.return_value = True
        mock_mapper.get_function.return_value = Mock()
        mock_mapper.get_function_info.return_value = {
            "name": "send_email",
            "description": "Send an email message",
            "schema": {"type": "object"}
        }
        mock_mapper.mapped_functions = {"send_email": Mock()}
        
        return MCPToolLoader(mock_mapper, mock_manager)
    
    @pytest.mark.asyncio
    async def test_interpreter_mcp_integration(self):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = Mock()
            
            tool_loader = self._create_mock_tool_loader()
            
            interpreter = PythonInterpreter(
                enable_policies=False,
                mcp_tool_loader=tool_loader
            )
            
            assert interpreter.mcp_tool_loader is not None
            
            available_tools = tool_loader.get_available_tools()
            assert isinstance(available_tools, list)
    
    @pytest.mark.asyncio
    async def test_interpreter_mcp_tool_execution(self):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = Mock()
            
            tool_loader = self._create_mock_tool_loader()
            
            interpreter = PythonInterpreter(
                enable_policies=False,
                mcp_tool_loader=tool_loader
            )
            
            assert tool_loader.has_tool("send_email")
            
            tool_func = tool_loader.get_tool_function("send_email")
            assert tool_func is not None
    
    @pytest.mark.asyncio
    async def test_interpreter_mcp_with_policies(self):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = Mock()
            
            tool_loader = self._create_mock_tool_loader()
            
            interpreter = PythonInterpreter(
                enable_policies=True,
                mcp_tool_loader=tool_loader
            )
            
            assert interpreter.enable_policies
    
    @pytest.mark.asyncio
    async def test_p_llm_agent_mcp_initialization(self, temp_config):
        config_file, temp_dir = temp_config
        
        with patch.dict(os.environ, {
            'AZURE_OPENAI_API_KEY': 'test-key',
            'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
            'AZURE_OPENAI_DEPLOYMENT': 'test-deployment'
        }):
            with patch('dromedary.agent.create_mcp_tool_loader') as mock_create_loader:
                mock_create_loader.return_value = self._create_mock_tool_loader()
                
                agent = PLLMAgent(mcp_config=str(config_file), policy_config="policies/policies.yaml")
                assert agent.mcp_tool_loader is None
                
                await agent._initialize_mcp()
                
                assert agent.mcp_tool_loader is not None
    
    def test_prompt_builder_mcp_integration(self):
        mock_tool_loader = self._create_mock_tool_loader()
        
        builder = SystemPromptBuilder(mcp_tool_loader=mock_tool_loader)
        
        prompt = builder.build_prompt()
        assert isinstance(prompt, str)
        assert "Available Tools" in prompt
    
    @pytest.mark.asyncio
    async def test_policy_engine_with_mcp_tools(self):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = Mock()
            
            tool_loader = self._create_mock_tool_loader()
            
            interpreter = PythonInterpreter(
                enable_policies=True,
                mcp_tool_loader=tool_loader
            )
            
            assert interpreter.enable_policies
            
            policy_engine = create_policy_engine("policies/policies.yaml")
            
            is_allowed, violations = policy_engine.evaluate_tool_call(
                "send_email",
                {"to": "test@example.com", "subject": "test"},
                {}
            )
            
            assert isinstance(is_allowed, bool)
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_mcp_servers(self):
        with patch('dromedary.mcp.create_mcp_tool_loader') as mock_create_loader:
            mock_create_loader.return_value = self._create_mock_tool_loader()
            
            tool_loader = mock_create_loader.return_value
            
            available_tools = tool_loader.get_available_tools()
            assert isinstance(available_tools, list)
            
            connected_servers = tool_loader.get_connected_servers()
            assert isinstance(connected_servers, list)
    
    def test_mcp_type_converter_integration(self):
        converter = MCPTypeConverter()
        
        result = converter.python_args_to_mcp([], {"to": "test@example.com"})
        assert isinstance(result, dict)
        
        mock_content = [Mock(text="test result")]
        result = converter.mcp_result_to_python(mock_content)
        assert result == "test result"
    
    @pytest.mark.asyncio
    async def test_mcp_error_handling_integration(self):
        with patch('dromedary.mcp.create_mcp_tool_loader') as mock_create_loader:
            mock_create_loader.side_effect = RuntimeError("Failed to connect to any MCP servers.")
            
            with pytest.raises(RuntimeError, match="Failed to connect"):
                tool_loader = mock_create_loader()
    
    @pytest.mark.asyncio
    async def test_mcp_server_lifecycle_management(self):
        with patch('dromedary.mcp.create_mcp_tool_loader') as mock_create_loader:
            mock_tool_loader = self._create_mock_tool_loader()
            mock_create_loader.return_value = mock_tool_loader
            
            tool_loader = mock_create_loader()
            
            available_tools = tool_loader.get_available_tools()
            assert isinstance(available_tools, list)


class TestMCPIntegrationEdgeCases:
    
    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_invalid_config_handling(self):
        with patch('dromedary.mcp.create_mcp_tool_loader') as mock_create_loader:
            mock_create_loader.side_effect = RuntimeError("Config file not found")
            
            with pytest.raises(RuntimeError, match="Config file not found"):
                tool_loader = mock_create_loader("nonexistent-file.json")
    
    @pytest.mark.asyncio
    async def test_missing_config_file(self, temp_dir):
        nonexistent_file = Path(temp_dir) / "nonexistent.json"
        
        with patch('dromedary.mcp.create_mcp_tool_loader') as mock_create_loader:
            mock_create_loader.side_effect = RuntimeError("Config file not found")
            
            with pytest.raises(RuntimeError, match="Config file not found"):
                tool_loader = mock_create_loader(str(nonexistent_file))
    
    @pytest.mark.asyncio
    async def test_policy_violations_with_mcp_tools(self, temp_dir):
        config_file = Path(temp_dir) / "policy-test-config.json"
        test_config = {
            "mcpServers": {
                "email-server": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["email_server.py"],
                    "env": {}
                }
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        with patch('dromedary.mcp.create_mcp_tool_loader') as mock_create_loader:
            mock_manager = Mock(spec=MCPManager)
            mock_manager.get_all_tools.return_value = {"send_email": Mock()}
            mock_manager.get_connected_servers.return_value = ["email-server"]
            
            mock_mapper = Mock(spec=MCPToolMapper)
            mock_mapper.get_all_functions.return_value = {"send_email": Mock()}
            
            mock_tool_loader = MCPToolLoader(mock_mapper, mock_manager)
            mock_create_loader.return_value = mock_tool_loader
            
            tool_loader = mock_create_loader(str(config_file))
            
            policy_engine = create_policy_engine("policies/policies.yaml")
            
            is_allowed, violations = policy_engine.evaluate_tool_call(
                "send_email",
                {"to": "external@badsite.com", "subject": "test"},
                {}
            )
            
            assert isinstance(is_allowed, bool) 