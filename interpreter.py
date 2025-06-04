import ast
import os
from datetime import datetime, timedelta, date, time, timezone
from enum import Enum
from typing import Any, Dict, Type, Set, List
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field, EmailStr

from tools import get_all_tools
from models import available_types
from policy_engine import policy_engine, PolicyViolationError
from capability import CapabilityValue, Capability, Source, SourceType


# TODO: more configurable interpreter like the execution_trace should be enabled / disabled. 
class PythonInterpreter:
    def __init__(self, enable_policies=True):
        self.enable_policies = enable_policies
        self.globals = {}
        self.tools = {}
        self.execution_trace = []  # Track actual function calls with arguments
        self._setup_environment()
        self._setup_tools()
        self._setup_ai_assistant()
    
    def _create_capability_value(self, value: Any, sources: list = None, dependencies: Set[CapabilityValue] = None) -> CapabilityValue:
        """Helper to create a CapabilityValue with proper sources and dependencies"""
        if sources is None:
            sources = []
        if dependencies is None:
            dependencies = set()
            
        capability = Capability()
        capability.sources = sources
        
        cap_value = CapabilityValue()
        cap_value.value = value
        cap_value.capability = capability
        cap_value.dependencies = dependencies
        return cap_value
    
    def _unwrap_value(self, obj: Any) -> Any:
        """Extract the actual value from a CapabilityValue, or return as-is"""
        if isinstance(obj, CapabilityValue):
            return obj.value
        return obj
    
    def _merge_dependencies(self, *cap_values) -> tuple[Set[CapabilityValue], list]:
        """Merge dependencies and sources from multiple CapabilityValues"""
        all_dependencies = set()
        all_sources_set = set()
        
        for val in cap_values:
            if isinstance(val, CapabilityValue):
                all_dependencies.add(val)
                all_dependencies.update(val.dependencies)
                for source in val.capability.sources:
                    all_sources_set.add((source.type, source.identifier))
        
        all_sources = [Source(type=src_type, identifier=src_id) for src_type, src_id in all_sources_set]
        return all_dependencies, all_sources
    
    def _create_system_capability_value(self, value: Any, dependencies: Set[CapabilityValue] = None) -> CapabilityValue:
        """Create a CapabilityValue for system-generated values (computations)"""
        if dependencies is None:
            dependencies = set()
            
        all_sources_set = set()
        for dep in dependencies:
            if isinstance(dep, CapabilityValue):
                for source in dep.capability.sources:
                    all_sources_set.add((source.type, source.identifier))
        
        system_source = Source(type=SourceType.SYSTEM, identifier="dromedary")
        all_sources_set.add((system_source.type, system_source.identifier))
        
        sources = [Source(type=src_type, identifier=src_id) for src_type, src_id in all_sources_set]
        return self._create_capability_value(value, sources, dependencies)
    
    def _setup_ai_assistant(self):
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
        system_source = Source(type=SourceType.SYSTEM, identifier="builtin")
        
        builtins = {
            'None': None,
            'True': True,
            'False': False,
            'abs': abs,
            'any': any,
            'all': all,
            'bool': bool,
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
            'datetime': datetime,
            'timedelta': timedelta,
            'date': date,
            'time': time,
            'timezone': timezone,
            'BaseModel': BaseModel,
            'Field': Field,
            'EmailStr': EmailStr,
        }
        
        for name, value in builtins.items():
            self.globals[name] = self._create_capability_value(value, [system_source])
        
        for model_type in available_types():
            self.globals[model_type.__name__] = self._create_capability_value(model_type, [system_source])
    
    def _wrapped_print(self, *args, **kwargs):
        """Wrapped print function that handles CapabilityValue objects"""
        unwrapped_args = [self._unwrap_value(arg) for arg in args]
        return print(*unwrapped_args, **kwargs)
    
    def _setup_tools(self):
        """Setup tools and add them to the globals"""
        tools = get_all_tools()
        for tool in tools:
            tool_name = tool.name
            wrapped_tool = self._create_capability_wrapped_tool(tool_name, tool._run)
            self.tools[tool_name] = wrapped_tool
            self.globals[tool_name] = self._create_capability_value(wrapped_tool, [Source(type=SourceType.SYSTEM, identifier="builtin")])
        
        self.globals['query_ai_assistant'] = self._create_capability_value(self._query_ai_assistant, [Source(type=SourceType.SYSTEM, identifier="builtin")])
    
    def _create_capability_wrapped_tool(self, tool_name: str, original_tool_func):
        """Create a wrapper function that validates policies and wraps results with TOOL capabilities"""
        def policy_validated_tool(*args, **kwargs):
            unwrapped_args = [self._unwrap_value(arg) for arg in args]
            unwrapped_kwargs = {k: self._unwrap_value(v) for k, v in kwargs.items()}
            
            additional_context = {}
            
            # Always collect capability values for all tools
            capability_values = {}
            for i, arg in enumerate(args):
                if isinstance(arg, CapabilityValue):
                    capability_values[f"arg_{i}"] = arg
            for k, v in kwargs.items():
                if isinstance(v, CapabilityValue):
                    capability_values[k] = v
            
            if capability_values:
                additional_context["capability_values"] = capability_values
            
            # TODO: file_id is a hard coded parameter for file operations. 
            # we should make it more generic and configurable. 
            if "file_id" in unwrapped_kwargs:
                file_id = unwrapped_kwargs["file_id"]
                try:
                    from tools import file_store
                    for file in file_store.files:
                        if file.id_ == file_id:
                            additional_context["file_content"] = file.content
                            break
                except Exception:
                    pass
            
            # Only check policies if enabled
            if self.enable_policies:
                is_allowed, violations = policy_engine.evaluate_tool_call(
                    tool_name, unwrapped_kwargs, additional_context
                )
                
                if not is_allowed:
                    violation_msg = f"Policy violation for {tool_name}: " + "; ".join(violations)
                    raise PolicyViolationError(violation_msg, violations)
            
            result = original_tool_func(*unwrapped_args, **unwrapped_kwargs)
            
            tool_source = Source(type=SourceType.TOOL, identifier=tool_name)
            return self._create_capability_value(result, [tool_source])
        
        return policy_validated_tool
    
    def _query_ai_assistant(self, query: str, output_schema: Type[BaseModel]) -> BaseModel:
        unwrapped_query = self._unwrap_value(query)
        unwrapped_schema = self._unwrap_value(output_schema)
        
        dependencies = set()
        all_sources_set = set()
        
        if isinstance(query, CapabilityValue):
            dependencies.add(query)
            dependencies.update(query.dependencies)
            for source in query.capability.sources:
                all_sources_set.add((source.type, source.identifier))
        
        if isinstance(output_schema, CapabilityValue):
            dependencies.add(output_schema)
            dependencies.update(output_schema.dependencies)
            for source in output_schema.capability.sources:
                all_sources_set.add((source.type, source.identifier))
        
        model_with_structure = self.llm.with_structured_output(unwrapped_schema)
        result = model_with_structure.invoke(unwrapped_query)
        
        system_source = Source(type=SourceType.SYSTEM, identifier="dromedary")
        all_sources_set.add((system_source.type, system_source.identifier))
        
        sources = [Source(type=src_type, identifier=src_id) for src_type, src_id in all_sources_set]
        return self._create_capability_value(result, sources, dependencies)
    
    def execute(self, code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
            result = None
            for node in tree.body:
                result = self._execute_node(node)
            return {
                "success": True,
                "result": result,
                "error": None
            }
        except SyntaxError as e:
            return {
                "success": False,
                "result": None,
                "error": f"Syntax error: {e}",
                "error_type": "syntax"
            }
        except PolicyViolationError as e:
            return {
                "success": False,
                "result": None,
                "error": f"Policy violation: {e}",
                "error_type": "policy"
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": f"Execution error: {e}",
                "error_type": "runtime"
            }
    
    def _execute_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Module):
            result = None
            for child in node.body:
                result = self._execute_node(child)
            return result
        
        elif isinstance(node, ast.Expr):
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.Assign):
            value = self._execute_node(node.value)
            for target in node.targets:
                self._assign_target(target, value)
            return value
        
        elif isinstance(node, ast.Name):
            if node.id in self.globals:
                return self.globals[node.id]
            raise NameError(f"name '{node.id}' is not defined")
        
        elif isinstance(node, ast.Constant):
            user_source = Source(type=SourceType.USER, identifier="literal")
            return self._create_capability_value(node.value, [user_source])
        
        elif isinstance(node, ast.Num):
            user_source = Source(type=SourceType.USER, identifier="literal")
            return self._create_capability_value(node.n, [user_source])
        
        elif isinstance(node, ast.Str):
            user_source = Source(type=SourceType.USER, identifier="literal")
            return self._create_capability_value(node.s, [user_source])
        
        elif isinstance(node, ast.List):
            result = []
            all_dependencies = set()
            
            for elem in node.elts:
                if isinstance(elem, ast.Starred):
                    starred_value = self._execute_node(elem.value)
                    starred_unwrapped = self._unwrap_value(starred_value)
                    if isinstance(starred_value, CapabilityValue):
                        all_dependencies.add(starred_value)
                        all_dependencies.update(starred_value.dependencies)
                    
                    if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                        result.extend(starred_unwrapped)
                    else:
                        raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
                else:
                    elem_value = self._execute_node(elem)
                    result.append(self._unwrap_value(elem_value))
                    if isinstance(elem_value, CapabilityValue):
                        all_dependencies.add(elem_value)
                        all_dependencies.update(elem_value.dependencies)
            
            return self._create_system_capability_value(result, all_dependencies)
        
        elif isinstance(node, ast.Tuple):
            result = []
            all_dependencies = set()
            
            for elem in node.elts:
                if isinstance(elem, ast.Starred):
                    starred_value = self._execute_node(elem.value)
                    starred_unwrapped = self._unwrap_value(starred_value)
                    if isinstance(starred_value, CapabilityValue):
                        all_dependencies.add(starred_value)
                        all_dependencies.update(starred_value.dependencies)
                    
                    if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                        result.extend(starred_unwrapped)
                    else:
                        raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
                else:
                    elem_value = self._execute_node(elem)
                    result.append(self._unwrap_value(elem_value))
                    if isinstance(elem_value, CapabilityValue):
                        all_dependencies.add(elem_value)
                        all_dependencies.update(elem_value.dependencies)
            
            return self._create_system_capability_value(tuple(result), all_dependencies)
        
        elif isinstance(node, ast.Starred):
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.Dict):
            keys = []
            values = []
            all_dependencies = set()
            
            for k, v in zip(node.keys, node.values):
                if k:
                    key_value = self._execute_node(k)
                    keys.append(self._unwrap_value(key_value))
                    if isinstance(key_value, CapabilityValue):
                        all_dependencies.add(key_value)
                        all_dependencies.update(key_value.dependencies)
                else:
                    keys.append(None)
                
                val_value = self._execute_node(v)
                values.append(self._unwrap_value(val_value))
                if isinstance(val_value, CapabilityValue):
                    all_dependencies.add(val_value)
                    all_dependencies.update(val_value.dependencies)
            
            return self._create_system_capability_value(dict(zip(keys, values)), all_dependencies)
        
        elif isinstance(node, ast.Set):
            result = set()
            all_dependencies = set()
            
            for elem in node.elts:
                if isinstance(elem, ast.Starred):
                    starred_value = self._execute_node(elem.value)
                    starred_unwrapped = self._unwrap_value(starred_value)
                    if isinstance(starred_value, CapabilityValue):
                        all_dependencies.add(starred_value)
                        all_dependencies.update(starred_value.dependencies)
                    
                    if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                        result.update(starred_unwrapped)
                    else:
                        raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
                else:
                    elem_value = self._execute_node(elem)
                    result.add(self._unwrap_value(elem_value))
                    if isinstance(elem_value, CapabilityValue):
                        all_dependencies.add(elem_value)
                        all_dependencies.update(elem_value.dependencies)
            
            return self._create_system_capability_value(result, all_dependencies)
        
        elif isinstance(node, ast.Call):
            func = self._execute_node(node.func)
            unwrapped_func = self._unwrap_value(func)
            args = []
            unwrapped_args = []
            all_dependencies = set()
            
            if isinstance(func, CapabilityValue):
                all_dependencies.add(func)
                all_dependencies.update(func.dependencies)
            
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    starred_value = self._execute_node(arg.value)
                    starred_unwrapped = self._unwrap_value(starred_value)
                    if isinstance(starred_value, CapabilityValue):
                        all_dependencies.add(starred_value)
                        all_dependencies.update(starred_value.dependencies)
                    
                    if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                        unwrapped_args.extend(starred_unwrapped)
                    else:
                        raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
                else:
                    arg_value = self._execute_node(arg)
                    args.append(arg_value)
                    unwrapped_args.append(self._unwrap_value(arg_value))
                    if isinstance(arg_value, CapabilityValue):
                        all_dependencies.add(arg_value)
                        all_dependencies.update(arg_value.dependencies)
            
            kwargs = {}
            unwrapped_kwargs = {}
            for kw in node.keywords:
                kw_value = self._execute_node(kw.value)
                kwargs[kw.arg] = kw_value
                unwrapped_kwargs[kw.arg] = self._unwrap_value(kw_value)
                if isinstance(kw_value, CapabilityValue):
                    all_dependencies.add(kw_value)
                    all_dependencies.update(kw_value.dependencies)
            
            func_name = None
            if hasattr(node.func, 'id'): # simple function call like `max()`
                func_name = node.func.id
            elif hasattr(node.func, 'attr'): # method call like `list.append()`
                func_name = node.func.attr
            
            if func_name:
                self._record_function_call(func_name, args, kwargs)
            
            if callable(unwrapped_func):
                if unwrapped_func == self._query_ai_assistant or unwrapped_func in self.tools.values():
                    # tools and AI assistant get original CapabilityValues
                    result = unwrapped_func(*args, **kwargs)
                else: # regular Python functions get unwrapped values
                    result = unwrapped_func(*unwrapped_args, **unwrapped_kwargs)
                
                if isinstance(result, CapabilityValue):
                    result.dependencies.update(all_dependencies)
                    return result
                else:
                    return self._create_system_capability_value(result, all_dependencies)
            else:
                raise TypeError(f"'{type(unwrapped_func).__name__}' object is not callable")
        
        elif isinstance(node, ast.Attribute):
            obj = self._execute_node(node.value)
            unwrapped_obj = self._unwrap_value(obj)
            result = getattr(unwrapped_obj, node.attr)
            
            dependencies = set()
            if isinstance(obj, CapabilityValue):
                dependencies.add(obj)
                dependencies.update(obj.dependencies)
            
            return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.Subscript):
            obj = self._execute_node(node.value)
            key = self._execute_node(node.slice)
            unwrapped_obj = self._unwrap_value(obj)
            unwrapped_key = self._unwrap_value(key)
            
            result = unwrapped_obj[unwrapped_key]
            
            dependencies = set()
            if isinstance(obj, CapabilityValue):
                dependencies.add(obj)
                dependencies.update(obj.dependencies)
            if isinstance(key, CapabilityValue):
                dependencies.add(key)
                dependencies.update(key.dependencies)
            
            return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.Index):
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.Slice):
            lower = self._execute_node(node.lower) if node.lower else None
            upper = self._execute_node(node.upper) if node.upper else None
            step = self._execute_node(node.step) if node.step else None
            
            lower_unwrapped = self._unwrap_value(lower) if lower is not None else None
            upper_unwrapped = self._unwrap_value(upper) if upper is not None else None
            step_unwrapped = self._unwrap_value(step) if step is not None else None
            
            return slice(lower_unwrapped, upper_unwrapped, step_unwrapped)
        
        elif isinstance(node, ast.IfExp):
            # Ternary operator: body if test else orelse
            test = self._execute_node(node.test)
            if test:
                return self._execute_node(node.body)
            else:
                return self._execute_node(node.orelse)
        
        elif isinstance(node, ast.BinOp):
            left = self._execute_node(node.left)
            right = self._execute_node(node.right)
            unwrapped_left = self._unwrap_value(left)
            unwrapped_right = self._unwrap_value(right)
            
            dependencies = set()
            if isinstance(left, CapabilityValue):
                dependencies.add(left)
                dependencies.update(left.dependencies)
            if isinstance(right, CapabilityValue):
                dependencies.add(right)
                dependencies.update(right.dependencies)
            
            if isinstance(node.op, ast.Add):
                result = unwrapped_left + unwrapped_right
            elif isinstance(node.op, ast.Sub):
                result = unwrapped_left - unwrapped_right
            elif isinstance(node.op, ast.Mult):
                result = unwrapped_left * unwrapped_right
            elif isinstance(node.op, ast.Div):
                result = unwrapped_left / unwrapped_right
            elif isinstance(node.op, ast.FloorDiv):
                result = unwrapped_left // unwrapped_right
            elif isinstance(node.op, ast.Mod):
                result = unwrapped_left % unwrapped_right
            elif isinstance(node.op, ast.Pow):
                result = unwrapped_left ** unwrapped_right
            elif isinstance(node.op, ast.LShift):
                result = unwrapped_left << unwrapped_right
            elif isinstance(node.op, ast.RShift):
                result = unwrapped_left >> unwrapped_right
            elif isinstance(node.op, ast.BitOr):
                result = unwrapped_left | unwrapped_right
            elif isinstance(node.op, ast.BitXor):
                result = unwrapped_left ^ unwrapped_right
            elif isinstance(node.op, ast.BitAnd):
                result = unwrapped_left & unwrapped_right
            
            return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.UnaryOp):
            operand = self._execute_node(node.operand)
            unwrapped_operand = self._unwrap_value(operand)
            
            dependencies = set()
            if isinstance(operand, CapabilityValue):
                dependencies.add(operand)
                dependencies.update(operand.dependencies)
            
            if isinstance(node.op, ast.UAdd):
                result = +unwrapped_operand
            elif isinstance(node.op, ast.USub):
                result = -unwrapped_operand
            elif isinstance(node.op, ast.Not):
                result = not unwrapped_operand
            elif isinstance(node.op, ast.Invert):
                result = ~unwrapped_operand
            
            return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.Compare):
            left = self._execute_node(node.left)
            unwrapped_left = self._unwrap_value(left)
            result = True
            dependencies = set()
            
            if isinstance(left, CapabilityValue):
                dependencies.add(left)
                dependencies.update(left.dependencies)
            
            for op, comparator in zip(node.ops, node.comparators):
                right = self._execute_node(comparator)
                unwrapped_right = self._unwrap_value(right)
                
                if isinstance(right, CapabilityValue):
                    dependencies.add(right)
                    dependencies.update(right.dependencies)
                
                if isinstance(op, ast.Eq):
                    result = unwrapped_left == unwrapped_right
                elif isinstance(op, ast.NotEq):
                    result = unwrapped_left != unwrapped_right
                elif isinstance(op, ast.Lt):
                    result = unwrapped_left < unwrapped_right
                elif isinstance(op, ast.LtE):
                    result = unwrapped_left <= unwrapped_right
                elif isinstance(op, ast.Gt):
                    result = unwrapped_left > unwrapped_right
                elif isinstance(op, ast.GtE):
                    result = unwrapped_left >= unwrapped_right
                elif isinstance(op, ast.Is):
                    result = unwrapped_left is unwrapped_right
                elif isinstance(op, ast.IsNot):
                    result = unwrapped_left is not unwrapped_right
                elif isinstance(op, ast.In):
                    result = unwrapped_left in unwrapped_right
                elif isinstance(op, ast.NotIn):
                    result = unwrapped_left not in unwrapped_right
                
                if not result:
                    break
                unwrapped_left = unwrapped_right
            
            return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.BoolOp):
            dependencies = set()
            
            if isinstance(node.op, ast.And):
                for value in node.values:
                    result_cap = self._execute_node(value)
                    result = self._unwrap_value(result_cap)
                    if isinstance(result_cap, CapabilityValue):
                        dependencies.add(result_cap)
                        dependencies.update(result_cap.dependencies)
                    if not result:
                        return self._create_system_capability_value(result, dependencies)
                return self._create_system_capability_value(result, dependencies)
            elif isinstance(node.op, ast.Or):
                for value in node.values:
                    result_cap = self._execute_node(value)
                    result = self._unwrap_value(result_cap)
                    if isinstance(result_cap, CapabilityValue):
                        dependencies.add(result_cap)
                        dependencies.update(result_cap.dependencies)
                    if result:
                        return self._create_system_capability_value(result, dependencies)
                return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.If):
            test = self._execute_node(node.test)
            unwrapped_test = self._unwrap_value(test)
            
            if unwrapped_test:
                result = None
                for stmt in node.body:
                    result = self._execute_node(stmt)
                return result
            elif node.orelse:
                result = None
                for stmt in node.orelse:
                    result = self._execute_node(stmt)
                return result
        
        elif isinstance(node, ast.For):
            target = node.target
            iter_obj = self._execute_node(node.iter)
            unwrapped_iter = self._unwrap_value(iter_obj)
            result = None
            
            for item in unwrapped_iter:
                item_cap = self._create_system_capability_value(item, {iter_obj} if isinstance(iter_obj, CapabilityValue) else set())
                self._assign_target(target, item_cap)
                result = None
                for stmt in node.body:
                    result = self._execute_node(stmt)
            
            return result
        
        elif isinstance(node, ast.While):
            result = None
            while True:
                test = self._execute_node(node.test)
                unwrapped_test = self._unwrap_value(test)
                if not unwrapped_test:
                    break
                for stmt in node.body:
                    result = self._execute_node(stmt)
            return result
        
        elif isinstance(node, ast.Return):
            if node.value:
                return self._execute_node(node.value)
            return None
        
        elif isinstance(node, ast.Pass):
            return None
        
        elif isinstance(node, ast.Break):
            raise Exception("break")
        
        elif isinstance(node, ast.Continue):
            raise Exception("continue")
        
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                as_name = alias.asname or module_name
                if module_name == "datetime":
                    import datetime as dt_module
                    self.globals[as_name] = dt_module
                elif module_name == "pydantic":
                    import pydantic as pyd_module
                    self.globals[as_name] = pyd_module
            return None
        
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            if module_name == "datetime":
                for alias in node.names:
                    import_name = alias.name
                    as_name = alias.asname or import_name
                    if import_name == "datetime":
                        self.globals[as_name] = datetime
                    elif import_name == "date":
                        self.globals[as_name] = date
                    elif import_name == "time":
                        self.globals[as_name] = time
                    elif import_name == "timedelta":
                        self.globals[as_name] = timedelta
                    elif import_name == "timezone":
                        self.globals[as_name] = timezone
            elif module_name == "pydantic":
                for alias in node.names:
                    import_name = alias.name
                    as_name = alias.asname or import_name
                    if import_name == "BaseModel":
                        self.globals[as_name] = BaseModel
                    elif import_name == "Field":
                        self.globals[as_name] = Field
                    elif import_name == "EmailStr":
                        self.globals[as_name] = EmailStr
            return None
        
        elif isinstance(node, ast.ClassDef):
            class_name = node.name
            bases = [self._execute_node(base) for base in node.bases]
            unwrapped_bases = [self._unwrap_value(base) for base in bases]
            
            class_dict = {'__module__': '__main__'}
            annotations = {}
            dependencies = set()
            
            for base in bases:
                if isinstance(base, CapabilityValue):
                    dependencies.add(base)
                    dependencies.update(base.dependencies)
            
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    field_name = stmt.target.id
                    field_type_cap = self._execute_node(stmt.annotation)
                    field_type = self._unwrap_value(field_type_cap)
                    annotations[field_name] = field_type
                    
                    if isinstance(field_type_cap, CapabilityValue):
                        dependencies.add(field_type_cap)
                        dependencies.update(field_type_cap.dependencies)
                    
                    if stmt.value:
                        default_value_cap = self._execute_node(stmt.value)
                        default_value = self._unwrap_value(default_value_cap)
                        class_dict[field_name] = default_value
                        
                        if isinstance(default_value_cap, CapabilityValue):
                            dependencies.add(default_value_cap)
                            dependencies.update(default_value_cap.dependencies)
            
            class_dict['__annotations__'] = annotations
            
            new_class = type(class_name, tuple(unwrapped_bases), class_dict)
            class_cap_value = self._create_system_capability_value(new_class, dependencies)
            self.globals[class_name] = class_cap_value
            return class_cap_value
        
        elif isinstance(node, ast.AnnAssign):
            return None
        
        elif isinstance(node, ast.JoinedStr):
            result = ""
            dependencies = set()
            
            for value in node.values:
                if isinstance(value, ast.Str):
                    result += value.s
                elif isinstance(value, ast.Constant):
                    result += str(value.value)
                elif isinstance(value, ast.FormattedValue):
                    val_cap = self._execute_node(value.value)
                    val = self._unwrap_value(val_cap)
                    if isinstance(val_cap, CapabilityValue):
                        dependencies.add(val_cap)
                        dependencies.update(val_cap.dependencies)
                    
                    if value.format_spec:
                        format_spec_cap = self._execute_node(value.format_spec)
                        format_spec = self._unwrap_value(format_spec_cap)
                        if isinstance(format_spec_cap, CapabilityValue):
                            dependencies.add(format_spec_cap)
                            dependencies.update(format_spec_cap.dependencies)
                        result += format(val, format_spec)
                    else:
                        result += str(val)
            
            return self._create_system_capability_value(result, dependencies)
        
        elif isinstance(node, ast.FormattedValue):
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.ListComp):
            result = []
            dependencies = set()
            
            def process_generators(generators, generator_index=0):
                if generator_index >= len(generators):
                    element_cap = self._execute_node(node.elt)
                    element = self._unwrap_value(element_cap)
                    result.append(element)
                    if isinstance(element_cap, CapabilityValue):
                        dependencies.add(element_cap)
                        dependencies.update(element_cap.dependencies)
                    return
                
                generator = generators[generator_index]
                iter_cap = self._execute_node(generator.iter)
                iter_obj = self._unwrap_value(iter_cap)
                if isinstance(iter_cap, CapabilityValue):
                    dependencies.add(iter_cap)
                    dependencies.update(iter_cap.dependencies)
                
                for iter_value in iter_obj:
                    old_globals = self.globals.copy()
                    try:
                        iter_cap_value = self._create_system_capability_value(iter_value, {iter_cap} if isinstance(iter_cap, CapabilityValue) else set())
                        self._assign_target(generator.target, iter_cap_value)
                        should_continue = True
                        for if_clause in generator.ifs:
                            if_cap = self._execute_node(if_clause)
                            if_result = self._unwrap_value(if_cap)
                            if isinstance(if_cap, CapabilityValue):
                                dependencies.add(if_cap)
                                dependencies.update(if_cap.dependencies)
                            if not if_result:
                                should_continue = False
                                break
                        
                        if should_continue:
                            process_generators(generators, generator_index + 1)
                    finally:
                        self.globals = old_globals
            
            process_generators(node.generators)
            return self._create_system_capability_value(result, dependencies)
        
        else:
            raise NotImplementedError(f"Node type {type(node).__name__} not implemented")

    def _assign_target(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name):
            self.globals[target.id] = value
            
            if self.execution_trace and self.execution_trace[-1]['result_assigned_to'] is None:
                self.execution_trace[-1]['result_assigned_to'] = target.id
        
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            unwrapped_value = self._unwrap_value(value)
            if not hasattr(unwrapped_value, '__iter__') or isinstance(unwrapped_value, (str, bytes)):
                raise TypeError(f"cannot unpack non-sequence {type(unwrapped_value).__name__}")
            
            try:
                values = list(unwrapped_value)
            except TypeError:
                raise TypeError(f"'{type(unwrapped_value).__name__}' object is not iterable")
            
            starred_indices = []
            for i, target_elem in enumerate(target.elts):
                if isinstance(target_elem, ast.Starred):
                    starred_indices.append(i)
            
            if len(starred_indices) > 1:
                raise SyntaxError("multiple starred expressions in assignment")
            elif len(starred_indices) == 1:
                starred_index = starred_indices[0]
                non_starred_count = len(target.elts) - 1
                
                if len(values) < non_starred_count:
                    raise ValueError(f"not enough values to unpack (expected at least {non_starred_count}, got {len(values)})")
                
                for i in range(starred_index):
                    item_cap = self._create_system_capability_value(values[i], {value} if isinstance(value, CapabilityValue) else set())
                    self._assign_target(target.elts[i], item_cap)
                
                starred_target = target.elts[starred_index]
                if isinstance(starred_target, ast.Starred):
                    remaining_after_star = len(target.elts) - starred_index - 1
                    star_values = values[starred_index:len(values) - remaining_after_star] if remaining_after_star > 0 else values[starred_index:]
                    star_cap = self._create_system_capability_value(star_values, {value} if isinstance(value, CapabilityValue) else set())
                    self._assign_target(starred_target.value, star_cap)
                
                remaining_targets = len(target.elts) - starred_index - 1
                for i in range(remaining_targets):
                    target_idx = starred_index + 1 + i
                    value_idx = len(values) - remaining_targets + i
                    item_cap = self._create_system_capability_value(values[value_idx], {value} if isinstance(value, CapabilityValue) else set())
                    self._assign_target(target.elts[target_idx], item_cap)
            else:
                if len(target.elts) != len(values):
                    raise ValueError(f"too many values to unpack (expected {len(target.elts)})")
                
                for target_elem, val in zip(target.elts, values):
                    val_cap = self._create_system_capability_value(val, {value} if isinstance(value, CapabilityValue) else set())
                    self._assign_target(target_elem, val_cap)
        
        elif isinstance(target, ast.Subscript):
            obj = self._execute_node(target.value)
            key = self._execute_node(target.slice)
            unwrapped_obj = self._unwrap_value(obj)
            unwrapped_key = self._unwrap_value(key)
            unwrapped_value = self._unwrap_value(value)
            unwrapped_obj[unwrapped_key] = unwrapped_value
        
        elif isinstance(target, ast.Attribute):
            obj = self._execute_node(target.value)
            unwrapped_obj = self._unwrap_value(obj)
            unwrapped_value = self._unwrap_value(value)
            setattr(unwrapped_obj, target.attr, unwrapped_value)
        
        else:
            raise NotImplementedError(f"Assignment to {type(target).__name__} not implemented")

    def _get_variable_name(self, value) -> str:
        if isinstance(value, CapabilityValue):
            for var_name, var_value in self.globals.items():
                if var_value is value:
                    return var_name
        return None
    
    def _extract_variable_names_from_container(self, container) -> List[str]:
        var_names = []
        
        unwrapped = self._unwrap_value(container)
        
        if isinstance(unwrapped, (list, tuple)):
            if isinstance(container, CapabilityValue):
                for var_name, var_value in self.globals.items():
                    if isinstance(var_value, CapabilityValue):
                        if self._unwrap_value(var_value) in unwrapped:
                            var_names.append(var_name)
            else:
                for item in unwrapped:
                    if isinstance(item, CapabilityValue):
                        var_name = self._get_variable_name(item)
                        if var_name:
                            var_names.append(var_name)
                    elif isinstance(item, (list, tuple)):
                        var_names.extend(self._extract_variable_names_from_container(item))
        return var_names
    
    def _record_function_call(self, func_name: str, args: list, kwargs: dict, result_var: str = None):
        """Record function calls with actual variable arguments"""
        arg_vars = []
        for arg in args:
            var_name = self._get_variable_name(arg)
            if var_name:
                arg_vars.append(var_name)
            else:
                container_vars = self._extract_variable_names_from_container(arg)
                arg_vars.extend(container_vars)
        
        kwarg_vars = {}
        for k, v in kwargs.items():
            var_name = self._get_variable_name(v)
            if var_name:
                kwarg_vars[k] = var_name
            else:
                container_vars = self._extract_variable_names_from_container(v)
                if container_vars:
                    kwarg_vars[k] = container_vars[0] if len(container_vars) == 1 else container_vars
        
        call_record = {
            'function': func_name,
            'args': arg_vars,
            'kwargs': kwarg_vars,
            'result_assigned_to': result_var
        }
        self.execution_trace.append(call_record)
        return call_record
    
    def get_execution_trace(self) -> list:
        """Return the execution trace for visualization"""
        return self.execution_trace.copy()
    
    def clear_execution_trace(self):
        """Clear the execution trace for a new execution"""
        self.execution_trace.clear()
    
    def reset_globals(self):
        """Reset globals to initial state"""
        self.globals.clear()
        self._setup_environment()
        self._setup_tools()


def run_interpreter(code: str) -> Dict[str, Any]:
    interpreter = PythonInterpreter()
    return interpreter.execute(code)


if __name__ == "__main__":
    code = """
emails = get_received_emails()
last_email = emails[-1]
print(f"Last email: {last_email.subject}")
"""
    
    try:
        result = run_interpreter(code)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}") 