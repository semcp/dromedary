import ast
import os
from enum import Enum
from typing import Any, Dict, Type, Optional, List
from langchain.chat_models import init_chat_model
from pydantic import BaseModel

from .policy.engine import create_policy_engine, PolicyViolationError, PolicyEngine
from .provenance_graph import ProvenanceGraph, ProvenanceTracker, CapabilityValue
from .executor import NodeExecutor
from .mcp.tool_loader import MCPToolLoader


class PythonInterpreter:
    def __init__(self, 
                 enable_policies: bool = True,
                 mcp_tool_loader: Optional["MCPToolLoader"] = None, 
                 policy_engine: Optional[PolicyEngine] = None):
        self.enable_policies = enable_policies
        self.policy_engine = policy_engine or create_policy_engine("policies/policies.yaml")
        self.mcp_tool_loader = mcp_tool_loader
        self.globals = {}
        self.tools = {}
        
        self.provenance_graph = ProvenanceGraph()
        self.provenance = ProvenanceTracker(self.provenance_graph)
        
        self.executor = NodeExecutor(self.globals, self.provenance)
        self.last_result: Optional[CapabilityValue] = None
        self._setup_environment()
        self._setup_tools()
        self._setup_ai_assistant()
    
    def _unwrap_value(self, obj: Any) -> Any:
        """Extract the actual value from a CapabilityValue, or return as-is"""
        return self.provenance.unwrap(obj)
    
    def _setup_ai_assistant(self):
        """Setup the AI assistant for structured output queries."""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = "o4-mini"
        api_version = "2025-01-01-preview"
        
        os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
        os.environ["OPENAI_API_VERSION"] = api_version
        
        self.llm = init_chat_model(
            "azure_openai:o4-mini",
            azure_deployment=deployment,
        )
    
    def _setup_environment(self):
        """Setup the built-in environment with system-sourced capabilities."""
        builtins = {
            'None': None,
            'True': True,
            'False': False,
            'abs': abs,
            'any': any,
            'all': all,
            'bool': bool,
            'dict': dict,
            'dir': dir,
            'divmod': divmod,
            'enumerate': enumerate,
            'float': float,
            'hash': hash,
            'int': int,
            'len': len,
            'list': list,
            'max': max,
            'min': min,
            'print': self._wrapped_print,
            'range': range,
            'repr': repr,
            'reversed': reversed,
            'set': set,
            'sorted': sorted,
            'str': str,
            'tuple': tuple,
            'type': lambda x: type(self._unwrap_value(x)).__name__,
            'zip': zip,
            'sum': sum,
            'ValueError': ValueError,
            'Enum': Enum,
        }
        
        for name, value in builtins.items():
            self.globals[name] = self.provenance.from_system(value, "builtin")
    
    def _wrapped_print(self, *args, dependencies: List[CapabilityValue] = None, **kwargs):
        """Wrapped print function that handles CapabilityValue objects and provenance."""
        unwrapped_args = [self._unwrap_value(arg) for arg in args]
        print(*unwrapped_args, **kwargs)
        dependencies = dependencies or []
        return self.provenance.from_computation(None, dependencies=dependencies)
    
    def _setup_tools(self):
        """Setup tools and add them to the globals"""
        if self.mcp_tool_loader:
            available_tools = self.mcp_tool_loader.get_available_tools()
            for tool_name in available_tools:
                tool_function = self.mcp_tool_loader.get_tool_function(tool_name)
                wrapped_tool = self._create_mcp_capability_wrapped_tool(tool_name, tool_function)
                wrapped_tool._needs_capability_values = True  # Mark as special function
                self.tools[tool_name] = wrapped_tool
                self.globals[tool_name] = self.provenance.from_system(wrapped_tool, "mcp")
        
        # Create a wrapper function to mark it as special
        def query_ai_assistant(query, output_schema, dependencies: List[CapabilityValue] = None):
            return self._query_ai_assistant(query, output_schema, dependencies)
        query_ai_assistant._needs_capability_values = True
        self.globals['query_ai_assistant'] = self.provenance.from_system(query_ai_assistant, "builtin")
    
    def _create_mcp_capability_wrapped_tool(self, tool_name: str, mcp_tool_func):
        """Create a wrapper function for MCP tools that validates policies and wraps results."""
        def mcp_policy_validated_tool(*args, dependencies: List[CapabilityValue] = None, **kwargs):
            unwrapped_args = [self._unwrap_value(arg) for arg in args]
            unwrapped_kwargs = {k: self._unwrap_value(v) for k, v in kwargs.items()}
            
            # Get tool schema to map positional arguments to parameter names
            tool_schema = self.mcp_tool_loader.get_tool_schema(tool_name) if self.mcp_tool_loader else None
            mapped_capability_values = self._map_args_to_parameters(
                tool_name, args, kwargs, tool_schema
            )
            
            additional_context = {
                "capability_values": mapped_capability_values,
                "provenance_graph": self.provenance_graph
            }
            
            # Add file content for file operations
            if "file_id" in unwrapped_kwargs:
                file_id = unwrapped_kwargs["file_id"]
                if self.mcp_tool_loader and self.mcp_tool_loader.has_tool("get_file_by_id"):
                    try:
                        file_func = self.mcp_tool_loader.get_tool_function("get_file_by_id")
                        file_data = file_func(file_id)
                        if hasattr(file_data, 'content'):
                            additional_context["file_content"] = file_data.content
                        elif isinstance(file_data, dict) and 'content' in file_data:
                            additional_context["file_content"] = file_data['content']
                    except Exception:
                        pass
            
            # Policy evaluation using injected policy engine
            if self.enable_policies:
                is_allowed, violations = self.policy_engine.evaluate_tool_call(
                    tool_name, unwrapped_kwargs, additional_context
                )
                
                if not is_allowed:
                    violation_msg = f"Policy violation for {tool_name}: " + "; ".join(violations)
                    raise PolicyViolationError(violation_msg, violations)
            
            result = mcp_tool_func(*unwrapped_args, **unwrapped_kwargs)
            
            dependencies = dependencies or []
            return self.provenance.from_tool(result, tool_name, dependencies=dependencies)
        
        return mcp_policy_validated_tool
    
    def _map_args_to_parameters(self, tool_name: str, args: tuple, kwargs: dict, tool_schema: dict) -> dict:
        """Map positional and keyword arguments to their proper parameter names with capability values."""
        mapped_values = {}
        
        # Add keyword arguments first
        for key, value in kwargs.items():
            if isinstance(value, CapabilityValue):
                mapped_values[key] = value
        
        # Map positional arguments to parameter names using schema
        if tool_schema and args:
            input_schema = tool_schema.get('inputSchema', {})
            properties = input_schema.get('properties', {})
            required_fields = input_schema.get('required', [])
            
            # Create ordered parameter list (required first, then optional)
            param_names = required_fields.copy()
            for param_name in properties.keys():
                if param_name not in required_fields:
                    param_names.append(param_name)
            
            # Map positional args to parameter names
            for i, arg in enumerate(args):
                if i < len(param_names) and isinstance(arg, CapabilityValue):
                    param_name = param_names[i]
                    mapped_values[param_name] = arg
        
        return mapped_values
        
    def _query_ai_assistant(self, query: str, output_schema: Type[BaseModel], dependencies: List[CapabilityValue] = None) -> BaseModel:
        """Query AI assistant with structured output capabilities."""
        unwrapped_query = self._unwrap_value(query)
        unwrapped_schema = self._unwrap_value(output_schema)
        
        # The 'dependencies' list is now passed directly from the executor
        dependencies = dependencies or []
        
        model_with_structure = self.llm.with_structured_output(unwrapped_schema)
        result = model_with_structure.invoke(unwrapped_query)
        
        # Pass the complete dependency list
        return self.provenance.from_computation(result, dependencies=dependencies)
    
    def execute(self, code: str) -> Dict[str, Any]:
        """Execute Python code using the NodeExecutor with proper error handling."""
        try:
            tree = ast.parse(code)
            result = self.executor.visit(tree)
            
            if isinstance(result, CapabilityValue):
                self.last_result = result
            else:
                self.last_result = None
                
            return {
                "success": True,
                "result": result,
                "error": None
            }
        except SyntaxError as e:
            self.last_result = None
            return {
                "success": False,
                "result": None,
                "error": f"Syntax error: {e}",
                "error_type": "syntax"
            }
        except PolicyViolationError as e:
            self.last_result = None
            return {
                "success": False,
                "result": None,
                "error": f"{e}",
                "error_type": "policy"
            }
        except Exception as e:
            self.last_result = None
            return {
                "success": False,
                "result": None,
                "error": f"{e}",
                "error_type": "runtime"
            }
    
    def get_execution_trace(self) -> list:
        """Return the execution trace for visualization"""
        return self.executor.execution_trace.copy()
    
    def clear_execution_trace(self):
        """Clear the execution trace for a new execution"""
        self.executor.execution_trace.clear()
    
    def reset_globals(self):
        """Reset globals to initial state"""
        self.globals.clear()
        self.provenance_graph = ProvenanceGraph()
        self.provenance = ProvenanceTracker(self.provenance_graph)
        self.last_result = None
        self._setup_environment()
        self._setup_tools()
        self.executor = NodeExecutor(self.globals, self.provenance)


def run_interpreter(code: str) -> Dict[str, Any]:
    """Factory function to create and run interpreter."""
    interpreter = PythonInterpreter()
    return interpreter.execute(code)
