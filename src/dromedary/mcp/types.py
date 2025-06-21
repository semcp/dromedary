"""
Type conversion utilities for MCP integration.
"""

import json
from typing import Any, Dict, List, Type, get_origin, get_args
from datetime import datetime
from pydantic import BaseModel


class MCPTypeConverter:
    """Handles type conversions between Python and MCP types."""
    
    @classmethod
    def python_type_to_json_schema(cls, python_type: Type) -> Dict[str, Any]:
        """Convert Python type annotation to JSON schema for MCP."""
        if python_type == str:
            return {"type": "string"}
        elif python_type == int:
            return {"type": "integer"}
        elif python_type == float:
            return {"type": "number"}
        elif python_type == bool:
            return {"type": "boolean"}
        elif python_type == datetime:
            return {"type": "string", "format": "date-time"}
        elif python_type == list:
            return {"type": "array"}
        elif python_type == dict:
            return {"type": "object"}
        elif get_origin(python_type) == list:
            args = get_args(python_type)
            if args:
                return {
                    "type": "array",
                    "items": cls.python_type_to_json_schema(args[0])
                }
            return {"type": "array"}
        elif get_origin(python_type) == dict:
            return {"type": "object"}
        elif hasattr(python_type, '__annotations__') and getattr(python_type, '__annotations__', {}):
            # Only treat as object if it actually has annotations (like Pydantic models)
            return {"type": "object"}
        else:
            return {"type": "string"}
    
    @classmethod
    def mcp_result_to_python(cls, mcp_result: Any) -> Any:
        """Convert MCP tool result to Python object."""
        if mcp_result is None:
            return None
        
        # Handle string results directly
        if isinstance(mcp_result, str):
            try:
                return json.loads(mcp_result)
            except json.JSONDecodeError:
                return mcp_result
        
        # Handle CallToolResult object
        if hasattr(mcp_result, 'content') and hasattr(mcp_result, 'isError'):
            # This is a CallToolResult object
            if mcp_result.isError:
                raise RuntimeError(f"MCP tool returned error: {mcp_result.content}")
            
            content_list = mcp_result.content
            if not content_list:
                return None
            
            if len(content_list) == 1:
                content = content_list[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except (json.JSONDecodeError, AttributeError):
                        return content.text
                else:
                    return str(content)
            
            # For multiple contents, try to parse each one
            results = []
            for content in content_list:
                if hasattr(content, 'text'):
                    try:
                        results.append(json.loads(content.text))
                    except json.JSONDecodeError:
                        results.append(content.text)
                else:
                    results.append(str(content))
            
            return results
        
        # Handle list results (legacy format)
        if isinstance(mcp_result, list):
            if not mcp_result:
                return None
            
            if len(mcp_result) == 1:
                content = mcp_result[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except (json.JSONDecodeError, AttributeError):
                        return content.text
                else:
                    return content
            
            # For multiple contents, try to parse each one
            results = []
            for content in mcp_result:
                if hasattr(content, 'text'):
                    try:
                        results.append(json.loads(content.text))
                    except json.JSONDecodeError:
                        results.append(content.text)
                else:
                    results.append(str(content))
            
            return results
        
        # Handle other types
        return mcp_result
    
    @classmethod
    def python_args_to_mcp(cls, args: List[Any], kwargs: Dict[str, Any], tool_schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert Python function arguments to MCP tool arguments using schema."""
        mcp_args = {}
        
        # First, add all keyword arguments
        for key, value in kwargs.items():
            mcp_args[key] = cls._convert_value(value)
        
        # Map positional arguments to parameter names using schema
        if args and tool_schema:
            param_names = cls._extract_parameter_order(tool_schema)
            
            # Map positional args to parameter names
            for i, arg in enumerate(args):
                if i < len(param_names):
                    param_name = param_names[i]
                    
                    # Don't override if already provided as keyword arg
                    if param_name not in mcp_args:
                        mcp_args[param_name] = cls._convert_value(arg)
                else:
                    # Fallback for extra args beyond schema
                    mcp_args[f"arg_{i}"] = cls._convert_value(arg)
        elif args:
            # Fallback to current behavior if no schema
            for i, arg in enumerate(args):
                mcp_args[f"arg_{i}"] = cls._convert_value(arg)
        
        return mcp_args
    
    @classmethod
    def _extract_parameter_order(cls, tool_schema: Dict[str, Any]) -> List[str]:
        """Extract parameter names in order: required first, then optional."""
        if not isinstance(tool_schema, dict) or 'properties' not in tool_schema:
            return []
        
        properties = tool_schema['properties']
        required = tool_schema.get('required', [])
        
        # Required parameters first, in the order they appear in required list
        param_order = required.copy()
        
        # Then optional parameters
        for param_name in properties.keys():
            if param_name not in required:
                param_order.append(param_name)
        
        return param_order
    
    @classmethod
    def _convert_value(cls, value: Any) -> Any:
        """Convert a single value for MCP."""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, BaseModel):
            return value.model_dump()
        elif hasattr(value, '__dict__'):
            return value.__dict__
        else:
            return value
    
    @classmethod
    def format_function_signature(cls, tool: Any) -> str:
        """Generate Python function signature from MCP tool schema."""
        schema = tool.inputSchema
        
        if not isinstance(schema, dict) or 'properties' not in schema:
            return f"def {tool.name}() -> Any:"
        
        properties = schema['properties']
        required = schema.get('required', [])
        
        params = []
        for param_name, param_schema in properties.items():
            param_type = cls._json_schema_to_python_type(param_schema)
            
            if param_name in required:
                params.append(f"{param_name}: {param_type}")
            else:
                params.append(f"{param_name}: {param_type} = None")
        
        params_str = ", ".join(params)
        return f"def {tool.name}({params_str}) -> Any:"
    
    @classmethod
    def _json_schema_to_python_type(cls, schema: Dict[str, Any]) -> str:
        """Convert JSON schema type to Python type string."""
        schema_type = schema.get('type', 'string')
        
        if schema_type == 'string':
            return 'str'
        elif schema_type == 'integer':
            return 'int'
        elif schema_type == 'number':
            return 'float'
        elif schema_type == 'boolean':
            return 'bool'
        elif schema_type == 'array':
            items_schema = schema.get('items', {})
            if items_schema:
                item_type = cls._json_schema_to_python_type(items_schema)
                return f'List[{item_type}]'
            else:
                return 'List[Any]'
        elif schema_type == 'object':
            return 'Dict[str, Any]'
        else:
            return 'Any' 