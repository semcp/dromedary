import unittest
import json
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


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


class TestMCPTypeConverter(unittest.TestCase):
    """Test MCP type conversion utilities."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before all tests."""
        # Prevent MCP client initialization for pure type testing
        os.environ['MCP_TESTING'] = 'true'
    
    def setUp(self):
        self.converter = MCPTypeConverter()
    
    def test_python_type_to_json_schema_basic_types(self):
        """Test basic Python type to JSON schema conversion."""
        test_cases = [
            (str, {"type": "string"}),
            (int, {"type": "integer"}),
            (float, {"type": "number"}),
            (bool, {"type": "boolean"}),
            (datetime, {"type": "string", "format": "date-time"}),
        ]
        
        for python_type, expected_schema in test_cases:
            with self.subTest(python_type=python_type):
                result = self.converter.python_type_to_json_schema(python_type)
                self.assertEqual(result, expected_schema)
    
    def test_python_type_to_json_schema_complex_types(self):
        """Test complex Python type to JSON schema conversion."""
        list_str_schema = self.converter.python_type_to_json_schema(List[str])
        expected = {"type": "array", "items": {"type": "string"}}
        self.assertEqual(list_str_schema, expected)
        
        list_int_schema = self.converter.python_type_to_json_schema(List[int])
        expected = {"type": "array", "items": {"type": "integer"}}
        self.assertEqual(list_int_schema, expected)
        
        dict_schema = self.converter.python_type_to_json_schema(Dict[str, Any])
        expected = {"type": "object"}
        self.assertEqual(dict_schema, expected)
        
        bare_list_schema = self.converter.python_type_to_json_schema(list)
        expected = {"type": "array"}
        self.assertEqual(bare_list_schema, expected)
    
    def test_python_type_to_json_schema_object_types(self):
        """Test object type to JSON schema conversion."""
        schema = self.converter.python_type_to_json_schema(UserModel)
        expected = {"type": "object"}
        self.assertEqual(schema, expected)
    
    def test_python_type_to_json_schema_unknown_types(self):
        """Test unknown type to JSON schema conversion defaults to string."""
        class CustomType:
            pass
        
        schema = self.converter.python_type_to_json_schema(CustomType)
        expected = {"type": "string"}
        self.assertEqual(schema, expected)
    
    def test_json_schema_to_python_type_basic(self):
        """Test JSON schema to Python type string conversion."""
        test_cases = [
            ({"type": "string"}, "str"),
            ({"type": "integer"}, "int"),
            ({"type": "number"}, "float"),
            ({"type": "boolean"}, "bool"),
            ({"type": "object"}, "Dict[str, Any]"),
        ]
        
        for schema, expected_type in test_cases:
            with self.subTest(schema=schema):
                result = self.converter._json_schema_to_python_type(schema)
                self.assertEqual(result, expected_type)
    
    def test_json_schema_to_python_type_array(self):
        """Test array JSON schema to Python type conversion."""
        schema = {"type": "array", "items": {"type": "string"}}
        result = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(result, "List[str]")
        
        schema = {"type": "array", "items": {"type": "integer"}}
        result = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(result, "List[int]")
        
        schema = {"type": "array"}
        result = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(result, "List[Any]")
    
    def test_json_schema_to_python_type_unknown(self):
        """Test unknown schema type defaults to Any."""
        schema = {"type": "unknown"}
        result = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(result, "Any")
        
        schema = {}
        result = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(result, "str")
    
    def test_python_args_to_mcp_basic(self):
        """Test basic Python arguments to MCP arguments conversion."""
        args = []
        kwargs = {"name": "test", "age": 25, "active": True}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {"name": "test", "age": 25, "active": True}
        self.assertEqual(result, expected)
    
    def test_python_args_to_mcp_positional_args(self):
        """Test positional arguments conversion."""
        args = ["hello", 42, True]
        kwargs = {}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {"arg_0": "hello", "arg_1": 42, "arg_2": True}
        self.assertEqual(result, expected)
    
    def test_python_args_to_mcp_mixed_args(self):
        """Test mixed positional and keyword arguments."""
        args = ["pos1", "pos2"]
        kwargs = {"kwarg1": "value1", "kwarg2": 99}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {
            "arg_0": "pos1",
            "arg_1": "pos2", 
            "kwarg1": "value1",
            "kwarg2": 99
        }
        self.assertEqual(result, expected)
    
    def test_python_args_to_mcp_datetime(self):
        """Test datetime argument conversion."""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        args = []
        kwargs = {"timestamp": dt}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {"timestamp": dt.isoformat()}
        self.assertEqual(result, expected)
    
    def test_python_args_to_mcp_pydantic_model(self):
        """Test Pydantic model argument conversion."""
        model = UserModel(name="Alice", age=30, email="alice@example.com")
        args = []
        kwargs = {"user": model}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {
            "user": {
                "name": "Alice",
                "age": 30,
                "email": "alice@example.com"
            }
        }
        self.assertEqual(result, expected)
    
    def test_python_args_to_mcp_custom_object(self):
        """Test custom object with __dict__ conversion."""
        class CustomObject:
            def __init__(self):
                self.prop1 = "value1"
                self.prop2 = 42
        
        obj = CustomObject()
        args = []
        kwargs = {"obj": obj}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {"obj": {"prop1": "value1", "prop2": 42}}
        self.assertEqual(result, expected)
    
    def test_mcp_result_to_python_empty(self):
        """Test empty MCP result conversion."""
        result = self.converter.mcp_result_to_python([])
        self.assertIsNone(result)
    
    def test_mcp_result_to_python_single_text(self):
        """Test single text content conversion."""
        mcp_result = [MockTextContent("Hello World")]
        result = self.converter.mcp_result_to_python(mcp_result)
        self.assertEqual(result, "Hello World")
    
    def test_mcp_result_to_python_single_json(self):
        """Test single JSON content conversion."""
        json_data = {"name": "test", "value": 42}
        mcp_result = [MockTextContent(json.dumps(json_data))]
        result = self.converter.mcp_result_to_python(mcp_result)
        self.assertEqual(result, json_data)
    
    def test_mcp_result_to_python_multiple_contents(self):
        """Test multiple content items conversion."""
        mcp_result = [
            MockTextContent("text1"),
            MockTextContent('{"key": "value"}')
        ]
        result = self.converter.mcp_result_to_python(mcp_result)
        expected = ["text1", {"key": "value"}]
        self.assertEqual(result, expected)
    
    def test_mcp_result_to_python_no_text_attribute(self):
        """Test content without text attribute."""
        class MockContent:
            def __init__(self, value):
                self.value = value
            
            def __str__(self):
                return f"MockContent({self.value})"
        
        mcp_result = [MockContent("test")]
        result = self.converter.mcp_result_to_python(mcp_result)
        
        self.assertIsInstance(result, MockContent)
        self.assertEqual(str(result), "MockContent(test)")
    
    def test_format_function_signature_no_schema(self):
        """Test function signature generation with no input schema."""
        tool = MockTool("test_tool")
        signature = self.converter.format_function_signature(tool)
        expected = "def test_tool() -> Any:"
        self.assertEqual(signature, expected)
    
    def test_format_function_signature_empty_schema(self):
        """Test function signature generation with empty schema."""
        tool = MockTool("test_tool", input_schema={})
        signature = self.converter.format_function_signature(tool)
        expected = "def test_tool() -> Any:"
        self.assertEqual(signature, expected)
    
    def test_format_function_signature_with_parameters(self):
        """Test function signature generation with parameters."""
        schema = {
            "type": "object",
            "properties": {
                "required_param": {"type": "string"},
                "optional_param": {"type": "integer"}
            },
            "required": ["required_param"]
        }
        tool = MockTool("test_tool", input_schema=schema)
        signature = self.converter.format_function_signature(tool)
        expected = "def test_tool(required_param: str, optional_param: int = None) -> Any:"
        self.assertEqual(signature, expected)
    
    def test_format_function_signature_complex_types(self):
        """Test function signature generation with complex types."""
        schema = {
            "type": "object",
            "properties": {
                "string_list": {"type": "array", "items": {"type": "string"}},
                "number_list": {"type": "array", "items": {"type": "number"}},
                "object_param": {"type": "object"}
            },
            "required": ["string_list"]
        }
        tool = MockTool("test_tool", input_schema=schema)
        signature = self.converter.format_function_signature(tool)
        expected = "def test_tool(string_list: List[str], number_list: List[float] = None, object_param: Dict[str, Any] = None) -> Any:"
        self.assertEqual(signature, expected)

    def test_roundtrip_conversion_basic_types(self):
        """Test roundtrip conversion: Python -> JSON Schema -> Python type string."""
        test_types = [str, int, float, bool]
        
        for py_type in test_types:
            with self.subTest(py_type=py_type):
                schema = self.converter.python_type_to_json_schema(py_type)
                type_str = self.converter._json_schema_to_python_type(schema)
                
                if py_type == str:
                    self.assertEqual(type_str, "str")
                elif py_type == int:
                    self.assertEqual(type_str, "int")
                elif py_type == float:
                    self.assertEqual(type_str, "float")
                elif py_type == bool:
                    self.assertEqual(type_str, "bool")
    
    def test_roundtrip_conversion_complex_types(self):
        """Test roundtrip conversion for complex types."""
        schema = self.converter.python_type_to_json_schema(List[str])
        type_str = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(type_str, "List[str]")
        
        schema = self.converter.python_type_to_json_schema(Dict[str, Any])
        type_str = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(type_str, "Dict[str, Any]")

    def test_edge_cases_nested_arrays(self):
        """Test edge cases with nested array types."""
        list_list_str = List[List[str]]
        schema = self.converter.python_type_to_json_schema(list_list_str)
        expected = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}
        self.assertEqual(schema, expected)
        
        type_str = self.converter._json_schema_to_python_type(schema)
        self.assertEqual(type_str, "List[List[str]]")

    def test_edge_cases_empty_data(self):
        """Test edge cases with empty or None data."""
        result = self.converter.python_args_to_mcp([], {})
        self.assertEqual(result, {})
        
        result = self.converter.mcp_result_to_python(None)
        self.assertIsNone(result)
        
        result = self.converter.mcp_result_to_python([])
        self.assertIsNone(result)

    def test_edge_cases_special_characters(self):
        """Test edge cases with special characters in strings."""
        args = []
        kwargs = {"special": "hello\nworld\t\"quoted\""}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {"special": "hello\nworld\t\"quoted\""}
        self.assertEqual(result, expected)

    def test_edge_cases_large_numbers(self):
        """Test edge cases with large numbers."""
        large_int = 9223372036854775807  # max int64
        large_float = 1.7976931348623157e+308  # close to max float64
        
        args = []
        kwargs = {"big_int": large_int, "big_float": large_float}
        
        result = self.converter.python_args_to_mcp(args, kwargs)
        expected = {"big_int": large_int, "big_float": large_float}
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main() 