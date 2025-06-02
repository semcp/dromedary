import inspect
from typing import List, Type, get_type_hints, get_origin, get_args
from langchain.tools import BaseTool
from pydantic import BaseModel
from tools import get_all_tools
from models import available_types

# this is just to help build a system prompt for the P-LLM agent given the tools.
class SystemPromptBuilder:
    def __init__(self):
        self.tools = get_all_tools()
        self.types = available_types()
    
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
    
    def _extract_tool_info(self, tool: BaseTool) -> dict:
        run_method = getattr(tool, '_run')
        signature = inspect.signature(run_method)
        type_hints = get_type_hints(run_method)
        
        parameters = []
        for param_name, param in signature.parameters.items():
            param_type = type_hints.get(param_name, 'Any')
            formatted_type = self._format_type_annotation(param_type)
            
            param_info = {
                'name': param_name,
                'type': formatted_type,
                'default': param.default if param.default != inspect.Parameter.empty else None,
                'required': param.default == inspect.Parameter.empty
            }
            parameters.append(param_info)
        
        return_type = type_hints.get('return', 'Any')
        formatted_return_type = self._format_type_annotation(return_type)
        
        return {
            'name': tool.name,
            'description': tool.description,
            'parameters': parameters,
            'return_type': formatted_return_type
        }
    
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
    
    def _generate_type_definitions(self) -> str:
        type_definitions = []
        
        for type_class in self.types:
            if hasattr(type_class, '__members__') and hasattr(type_class, '__bases__'):
                from enum import Enum
                if any(issubclass(base, Enum) for base in type_class.__bases__ if base != object):
                    enum_name = type_class.__name__
                    members = [f"    {name} = '{value.value}'" for name, value in type_class.__members__.items()]
                    type_def = f"class {enum_name}(Enum):\n" + "\n".join(members)
                    type_definitions.append(type_def)
                    continue
            
            if hasattr(type_class, '__annotations__'):
                class_name = type_class.__name__
                fields = []
                
                if hasattr(type_class, 'model_fields'):
                    base_class = "BaseModel" if issubclass(type_class, BaseModel) else ""
                    class_header = f"class {class_name}({base_class}):" if base_class else f"class {class_name}:"
                    
                    for field_name, field_info in type_class.model_fields.items():
                        field_type = self._format_type_annotation(field_info.annotation)
                        
                        field_parts = []
                        if hasattr(field_info, 'description') and field_info.description:
                            field_parts.append(f"description='{field_info.description}'")
                        
                        default_part = self._format_field_default(field_info)
                        if default_part:
                            field_parts.append(default_part)
                        
                        if field_parts:
                            field_def = f"    {field_name}: {field_type} = Field({', '.join(field_parts)})"
                        else:
                            field_def = f"    {field_name}: {field_type} = Field()"
                        
                        fields.append(field_def)
                    
                    if fields:
                        type_def = class_header + "\n" + "\n".join(fields)
                    else:
                        type_def = class_header + "\n    pass"
                else:
                    type_def = f"class {class_name}:\n    pass"
                
                type_definitions.append(type_def)
        
        return "\n\n".join(type_definitions)
    
    def build_prompt(self) -> str:
        prompt_parts = []
        
        prompt_parts.append("# Available Data Types")
        prompt_parts.append("")
        prompt_parts.append("The following data types are available for use:")
        prompt_parts.append("")
        prompt_parts.append("```python")
        prompt_parts.append(self._generate_type_definitions())
        prompt_parts.append("```")
        prompt_parts.append("")
        
        prompt_parts.append("# Available Tools")
        prompt_parts.append("")
        prompt_parts.append("You have access to the following tools/functions:")
        prompt_parts.append("")
        prompt_parts.append("```python")
        
        for tool in self.tools:
            tool_info = self._extract_tool_info(tool)
            
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