import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dromedary.interpreter import PythonInterpreter
from dromedary.mcp import create_mcp_tool_loader


def create_mock_llm():
    mock_llm = Mock()
    
    def mock_with_structured_output(schema):
        mock_structured = Mock()
        
        def mock_invoke(query):
            if hasattr(schema, '__name__') and 'email' in schema.__name__.lower():
                class MockEmailExtraction:
                    def __init__(self):
                        self.email = "test@example.com"
                return MockEmailExtraction()
            else:
                return Mock()
        
        mock_structured.invoke = mock_invoke
        return mock_structured
    
    mock_llm.with_structured_output = mock_with_structured_output
    return mock_llm


class TestPolicyViolationIntegration:
    
    @pytest.fixture
    def config_path(self):
        return "mcp_servers/mcp-servers-config.json"
    
    @pytest.fixture
    def test_code_file(self):
        return "tests/testdata/test2.py"
    
    @pytest.fixture
    def test_code_content(self, test_code_file):
        with open(test_code_file, 'r') as f:
            return f.read().strip()
    
    @pytest.fixture
    def tool_loader(self, config_path):
        if not Path(config_path).exists():
            pytest.skip(f"Config file not found: {config_path}")
        
        try:
            return create_mcp_tool_loader(config_path)
        except Exception as e:
            pytest.skip(f"Failed to initialize MCP connections: {e}")
    
    def test_policy_violation_with_untrusted_email_source(self, tool_loader, test_code_content):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = create_mock_llm()
            
            interpreter = PythonInterpreter(
                enable_policies=True, 
                mcp_tool_loader=tool_loader
            )
            
            result = interpreter.execute(test_code_content)
            
            assert result['success'] is False
            assert result.get('error_type') == 'policy'
            assert 'Policy violation for send_email' in result['error']
            assert 'Cannot send email to address from untrusted source' in result['error']
            assert 'get_received_emails' in result['error']
    
    def test_interpreter_with_policies_disabled_should_work(self, tool_loader, test_code_content):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = create_mock_llm()
            
            interpreter = PythonInterpreter(
                enable_policies=False,
                mcp_tool_loader=tool_loader
            )
            
            result = interpreter.execute(test_code_content)
            
            assert result['success'] is True or 'email sent successfully' in str(result.get('result', '')).lower()
    
    def test_mcp_tool_loader_initialization(self, config_path):
        if not Path(config_path).exists():
            pytest.skip(f"Config file not found: {config_path}")
        
        tool_loader = create_mcp_tool_loader(config_path)
        
        available_tools = tool_loader.get_available_tools()
        connected_servers = tool_loader.get_connected_servers()
        
        assert isinstance(available_tools, list)
        assert isinstance(connected_servers, list)
        assert len(available_tools) > 0
        assert len(connected_servers) > 0
        
        expected_tools = ['send_email', 'get_received_emails', 'search_contacts_by_email']
        for tool in expected_tools:
            assert tool in available_tools, f"Expected tool {tool} not found in available tools: {available_tools}"
    
    def test_specific_policy_violation_message(self, tool_loader, test_code_content):
        with patch('dromedary.interpreter.init_chat_model') as mock_init_chat:
            mock_init_chat.return_value = create_mock_llm()
            
            interpreter = PythonInterpreter(
                enable_policies=True,
                mcp_tool_loader=tool_loader
            )
            
            result = interpreter.execute(test_code_content)
            
            assert result['success'] is False
            assert result.get('error_type') == 'policy'
            
            error_message = result['error']
            assert 'Use the search_contacts_by_name or search_contacts_by_email tools' in error_message 