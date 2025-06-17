import inspect
from typing import get_type_hints, get_origin, get_args, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel

from dromedary_mcp.tool_loader import MCPToolLoader

# this is just to help build a system prompt for the P-LLM agent given the tools.
class SystemPromptBuilder:
    def __init__(self, mcp_tool_loader: Optional["MCPToolLoader"] = None):
        self.mcp_tool_loader = mcp_tool_loader
    
    def _format_type_annotation(self, annotation) -> str:
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        elif hasattr(annotation, '_name'):
            return annotation._name
        elif get_origin(annotation) is list:
            args = get_args(annotation)
            if args:
                return f"List[{self._format_type_annotation(args[0])}]"
            return "List"
        elif get_origin(annotation) is dict:
            args = get_args(annotation)
            if len(args) == 2:
                return f"Dict[{self._format_type_annotation(args[0])}, {self._format_type_annotation(args[1])}]"
            return "Dict"
        elif str(annotation).startswith('typing.Union'):
            args = get_args(annotation)
            if len(args) == 2 and type(None) in args:
                non_none_type = args[0] if args[1] is type(None) else args[1]
                return f"Optional[{self._format_type_annotation(non_none_type)}]"
            return f"Union[{', '.join(self._format_type_annotation(arg) for arg in args)}]"
        else:
            return str(annotation).replace('typing.', '')
    
    def _extract_mcp_tool_info(self, tool_name: str, tool_schema: dict) -> dict:
        parameters = []
        
        input_schema = tool_schema.get('inputSchema', {})
        properties = input_schema.get('properties', {})
        required_fields = input_schema.get('required', [])
        
        # Order parameters: required first, then optional
        param_order = required_fields.copy()
        for param_name in properties.keys():
            if param_name not in required_fields:
                param_order.append(param_name)
        
        for param_name in param_order:
            if param_name in properties:
                param_schema = properties[param_name]
                python_type = self._json_schema_to_python_type(param_schema)
                param_info = {
                    'name': param_name,
                    'type': python_type,
                    'default': None,
                    'required': param_name in required_fields
                }
                parameters.append(param_info)
        
        return {
            'name': tool_name,
            'description': tool_schema.get('description', 'MCP tool'),
            'parameters': parameters,
            'return_type': 'Any'
        }
    
    def _json_schema_to_python_type(self, schema: dict) -> str:
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
                item_type = self._json_schema_to_python_type(items_schema)
                return f'List[{item_type}]'
            else:
                return 'List[Any]'
        elif schema_type == 'object':
            return 'Dict[str, Any]'
        else:
            return 'Any'
    
    def _generate_function_signature(self, tool_info: dict) -> str:
        params = []
        for param in tool_info['parameters']:
            param_str = f"{param['name']}: {param['type']}"
            if not param['required'] and param['default'] is not None:
                if param['default'] == []:
                    param_str += " = []"
                elif param['default'] == {}:
                    param_str += " = {}"
                elif isinstance(param['default'], str):
                    param_str += f" = '{param['default']}'"
                else:
                    param_str += f" = {param['default']}"
            elif not param['required']:
                param_str += " = None"
            params.append(param_str)
        
        params_str = ", ".join(params)
        return f"def {tool_info['name']}({params_str}) -> {tool_info['return_type']}:"
    
    def _format_field_default(self, field_info) -> str:
        if hasattr(field_info, 'default_factory') and field_info.default_factory is not None:
            if field_info.default_factory.__name__ == 'list':
                return "default_factory=list"
            elif field_info.default_factory.__name__ == 'dict':
                return "default_factory=dict"
            else:
                return f"default_factory={field_info.default_factory.__name__}"
        elif hasattr(field_info, 'default') and field_info.default is not None:
            if hasattr(field_info.default, '__name__'):
                return f"default={field_info.default.__name__}.{field_info.default.name}"
            elif isinstance(field_info.default, str):
                return f"default='{field_info.default}'"
            elif isinstance(field_info.default, bool):
                return f"default={field_info.default}"
            else:
                return f"default={field_info.default}"
        return ""
    
    def build_prompt(self) -> str:
        if self.mcp_tool_loader is None:
            raise ValueError("MCP tool loader is not initialized")

        prompt_parts = []
        
        prompt_parts.append("# Available Tools")
        prompt_parts.append("")
        prompt_parts.append("You have access to the following tools/functions:")
        prompt_parts.append("")
        prompt_parts.append("```python")

        prompt_parts.append("def query_ai_assistant(query: str, output_schema: BaseModel) -> Any:")
        prompt_parts.append('    """Queries a Large Language Model with `query` and returns the language model\'s output. It must be used to process')
        prompt_parts.append("unstructured data into structured one.")
        prompt_parts.append("It is absolutely imperative that you use this function to parse data whose structure you don't know insted of parsing using")
        prompt_parts.append("regular expressions and/or")
        prompt_parts.append("string manipulation.")
        prompt_parts.append("There is no need to specify the expected output format in the query itself as the format will be specified on the side with")
        prompt_parts.append("`output_schema`")
        prompt_parts.append("with the build-in API of the assistant.")
        prompt_parts.append(":param query: a string with the query. Make sure to provide sufficient instructions to the AI assistant so that it can")
        prompt_parts.append("understand what it needs to do.")
        prompt_parts.append("Avoid just passing it tool outputs without additional instructions.")
        prompt_parts.append(":param output_schema: a Pydantic BaseModel class that specifies the expected output format from the model.")
        prompt_parts.append("The fields should have types as specific as possible to make sure the parsing is correct and accurate.")
        prompt_parts.append("allowed types are:")
        prompt_parts.append("- `int`")
        prompt_parts.append("- `str`")
        prompt_parts.append("- `float`")
        prompt_parts.append("- `bool`")
        prompt_parts.append("- `datetime.datetime` (assume `datetime` is imported from `datetime`)")
        prompt_parts.append("- `enum.Enum` classes")
        prompt_parts.append("- `pydantic.BaseModel` classes that you can define (assume that `BaseModel` is imported from `pydantic`) or are already")
        prompt_parts.append("defined in these instructions.")
        prompt_parts.append('- `pydantic.EmailStr` (assume that `EmailStr` is imported from `pydantic`)"""')
        prompt_parts.append("    ...")
        prompt_parts.append("")
        
        available_tool_names = self.mcp_tool_loader.get_available_tools()
        for tool_name in available_tool_names:
            tool_schema = self.mcp_tool_loader.get_tool_schema(tool_name)
            if tool_schema:
                tool_info = self._extract_mcp_tool_info(tool_name, tool_schema)
                
                prompt_parts.append(self._generate_function_signature(tool_info))
                prompt_parts.append(f'    """{tool_info["description"]}"""')
                prompt_parts.append("    ...")
                prompt_parts.append("")
        
        prompt_parts.append("```")
        
        return "\n".join(prompt_parts)


def build_system_prompt() -> str:
    builder = SystemPromptBuilder()
    return builder.build_prompt()


if __name__ == "__main__":
    prompt = build_system_prompt()
    print(prompt) 