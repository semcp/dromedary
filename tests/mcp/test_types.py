import json
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import pytest


# Add the project root to path 
sys.path.insert(0, os.path.abspath('.'))

from dromedary.mcp.types import MCPTypeConverter


class UserModel(BaseModel):
    name: str
    age: int
    email: Optional[str] = None


class MockTool:
    """Mock MCP Tool for testing."""
    def __init__(self, name, description="Test tool", input_schema=None):
        self.name = name
        self.description = description
        self.inputSchema = input_schema or {}


class MockTextContent:
    """Mock MCP TextContent for testing."""
    def __init__(self, text):
        self.text = text


@pytest.fixture
def converter():
    os.environ['MCP_TESTING'] = 'true'
    return MCPTypeConverter()


def test_python_type_to_json_schema_basic_types(converter):
    """Test basic Python type to JSON schema conversion."""
    test_cases = [
        (str, {"type": "string"}),
        (int, {"type": "integer"}),
        (float, {"type": "number"}),
        (bool, {"type": "boolean"}),
        (datetime, {"type": "string", "format": "date-time"}),
    ]
    
    for python_type, expected_schema in test_cases:
        result = converter.python_type_to_json_schema(python_type)
        assert result == expected_schema


def test_python_type_to_json_schema_complex_types(converter):
    """Test complex Python type to JSON schema conversion."""
    list_str_schema = converter.python_type_to_json_schema(List[str])
    expected = {"type": "array", "items": {"type": "string"}}
    assert list_str_schema == expected
    
    list_int_schema = converter.python_type_to_json_schema(List[int])
    expected = {"type": "array", "items": {"type": "integer"}}
    assert list_int_schema == expected
    
    dict_schema = converter.python_type_to_json_schema(Dict[str, Any])
    expected = {"type": "object"}
    assert dict_schema == expected
    
    bare_list_schema = converter.python_type_to_json_schema(list)
    expected = {"type": "array"}
    assert bare_list_schema == expected


def test_python_type_to_json_schema_object_types(converter):
    """Test object type to JSON schema conversion."""
    schema = converter.python_type_to_json_schema(UserModel)
    expected = {"type": "object"}
    assert schema == expected


def test_python_type_to_json_schema_unknown_types(converter):
    """Test unknown type to JSON schema conversion defaults to string."""
    class CustomType:
        pass
    
    schema = converter.python_type_to_json_schema(CustomType)
    expected = {"type": "string"}
    assert schema == expected


def test_json_schema_to_python_type_basic(converter):
    """Test JSON schema to Python type string conversion."""
    test_cases = [
        ({"type": "string"}, "str"),
        ({"type": "integer"}, "int"),
        ({"type": "number"}, "float"),
        ({"type": "boolean"}, "bool"),
        ({"type": "object"}, "Dict[str, Any]"),
    ]
    
    for schema, expected_type in test_cases:
        result = converter._json_schema_to_python_type(schema)
        assert result == expected_type


def test_json_schema_to_python_type_array(converter):
    """Test array JSON schema to Python type conversion."""
    schema = {"type": "array", "items": {"type": "string"}}
    result = converter._json_schema_to_python_type(schema)
    assert result == "List[str]"
    
    schema = {"type": "array", "items": {"type": "integer"}}
    result = converter._json_schema_to_python_type(schema)
    assert result == "List[int]"
    
    schema = {"type": "array"}
    result = converter._json_schema_to_python_type(schema)
    assert result == "List[Any]"


def test_json_schema_to_python_type_unknown(converter):
    """Test unknown schema type defaults to Any."""
    schema = {"type": "unknown"}
    result = converter._json_schema_to_python_type(schema)
    assert result == "Any"
    
    schema = {}
    result = converter._json_schema_to_python_type(schema)
    assert result == "str"


def test_python_args_to_mcp_basic(converter):
    """Test basic Python arguments to MCP arguments conversion."""
    args = []
    kwargs = {"name": "test", "age": 25, "active": True}
    
    result = converter.python_args_to_mcp(args, kwargs)
    expected = {"name": "test", "age": 25, "active": True}
    assert result == expected


def test_python_args_to_mcp_positional_args(converter):
    """Test positional arguments conversion."""
    args = ["hello", 42, True]
    kwargs = {}
    
    result = converter.python_args_to_mcp(args, kwargs)
    expected = {"arg_0": "hello", "arg_1": 42, "arg_2": True}
    assert result == expected


def test_python_args_to_mcp_mixed_args(converter):
    """Test mixed positional and keyword arguments."""
    args = ["pos1", "pos2"]
    kwargs = {"kwarg1": "value1", "kwarg2": 99}
    
    result = converter.python_args_to_mcp(args, kwargs)
    expected = {
        "arg_0": "pos1",
        "arg_1": "pos2", 
        "kwarg1": "value1",
        "kwarg2": 99
    }
    assert result == expected


def test_python_args_to_mcp_datetime(converter):
    """Test datetime argument conversion."""
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    args = []
    kwargs = {"timestamp": dt}
    
    result = converter.python_args_to_mcp(args, kwargs)
    expected = {"timestamp": dt.isoformat()}
    assert result == expected


def test_python_args_to_mcp_pydantic_model(converter):
    """Test Pydantic model argument conversion."""
    model = UserModel(name="Alice", age=30, email="alice@example.com")
    args = []
    kwargs = {"user": model}
    
    result = converter.python_args_to_mcp(args, kwargs)
    expected = {
        "user": {
            "name": "Alice",
            "age": 30,
            "email": "alice@example.com"
        }
    }
    assert result == expected


def test_python_args_to_mcp_custom_object(converter):
    """Test custom object with __dict__ conversion."""
    class CustomObject:
        def __init__(self):
            self.prop1 = "value1"
            self.prop2 = 42
    
    obj = CustomObject()
    args = []
    kwargs = {"obj": obj}
    
    result = converter.python_args_to_mcp(args, kwargs)
    expected = {"obj": {"prop1": "value1", "prop2": 42}}
    assert result == expected


def test_mcp_result_to_python_empty(converter):
    """Test empty MCP result conversion."""
    result = converter.mcp_result_to_python([])
    assert result is None


def test_mcp_result_to_python_single_text(converter):
    """Test single text content conversion."""
    content = MockTextContent("Hello world")
    result = converter.mcp_result_to_python([content])
    assert result == "Hello world"


def test_mcp_result_to_python_single_json(converter):
    """Test single JSON content conversion."""
    content = MockTextContent('{"key": "value"}')
    result = converter.mcp_result_to_python([content])
    assert result == {"key": "value"}


def test_mcp_result_to_python_multiple_contents(converter):
    """Test multiple content items conversion."""
    content1 = MockTextContent("First part")
    content2 = MockTextContent("Second part")
    result = converter.mcp_result_to_python([content1, content2])
    assert result == ["First part", "Second part"]


def test_mcp_result_to_python_no_text_attribute(converter):
    """Test content without text attribute."""
    class MockContent:
        def __init__(self, value):
            self.value = value
        
        def __str__(self):
            return self.value
    
    content = MockContent("Content without text attribute")
    result = converter.mcp_result_to_python([content])
    assert str(result) == "Content without text attribute"


def test_format_function_signature_no_schema(converter):
    """Test function signature generation with no input schema."""
    tool = MockTool("test_tool")
    signature = converter.format_function_signature(tool)
    expected = "def test_tool() -> Any:"
    assert signature == expected


def test_format_function_signature_empty_schema(converter):
    """Test function signature generation with empty schema."""
    tool = MockTool("test_tool", input_schema={})
    signature = converter.format_function_signature(tool)
    expected = "def test_tool() -> Any:"
    assert signature == expected


def test_format_function_signature_with_parameters(converter):
    """Test function signature generation with parameters."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "active": {"type": "boolean"}
        }
    }
    tool = MockTool("test_tool", input_schema=schema)
    signature = converter.format_function_signature(tool)
    expected = "def test_tool(name: str = None, age: int = None, active: bool = None) -> Any:"
    assert signature == expected


def test_format_function_signature_complex_types(converter):
    """Test function signature generation with complex types."""
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"}
            },
            "config": {"type": "object"}
        }
    }
    tool = MockTool("test_tool", input_schema=schema)
    signature = converter.format_function_signature(tool)
    expected = "def test_tool(items: List[str] = None, config: Dict[str, Any] = None) -> Any:"
    assert signature == expected


def test_roundtrip_conversion_basic_types(converter):
    """Test roundtrip conversion: Python -> JSON Schema -> Python type string."""
    test_cases = [
        ("hello", str),
        (42, int),
        (3.14, float),
        (True, bool)
    ]
    
    for value, value_type in test_cases:
        args = []
        kwargs = {"param": value}
        
        mcp_args = converter.python_args_to_mcp(args, kwargs)
        assert mcp_args["param"] == value


def test_roundtrip_conversion_complex_types(converter):
    """Test roundtrip conversion for complex types."""
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    model = UserModel(name="Test", age=25)
    
    args = []
    kwargs = {"timestamp": dt, "user": model}
    
    mcp_args = converter.python_args_to_mcp(args, kwargs)
    assert mcp_args["timestamp"] == dt.isoformat()
    assert mcp_args["user"]["name"] == "Test"


def test_edge_cases_nested_arrays(converter):
    """Test edge cases with nested array types."""
    schema = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}
    result = converter._json_schema_to_python_type(schema)
    assert result == "List[List[str]]"


def test_edge_cases_empty_data(converter):
    """Test edge cases with empty or None data."""
    result = converter.python_args_to_mcp([], {})
    assert result == {}
    
    result = converter.mcp_result_to_python([])
    assert result is None


def test_edge_cases_special_characters(converter):
    """Test edge cases with special characters in strings."""
    args = []
    kwargs = {"text": "Special chars: !@#$%^&*()"}
    
    result = converter.python_args_to_mcp(args, kwargs)
    assert result["text"] == "Special chars: !@#$%^&*()"


def test_edge_cases_large_numbers(converter):
    """Test edge cases with large numbers."""
    large_int = 2**63 - 1  
    large_float = 1.7976931348623157e+308
    
    args = []
    kwargs = {"big_int": large_int, "big_float": large_float}
    
    result = converter.python_args_to_mcp(args, kwargs)
    assert result["big_int"] == large_int
    assert result["big_float"] == large_float 