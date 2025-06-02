import ast
import os
from datetime import datetime, timedelta, date, time, timezone
from enum import Enum
from typing import Any, Dict, Type
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field, EmailStr

from tools import get_all_tools
from models import available_types
from policy_engine import policy_engine, PolicyViolationError


class PythonInterpreter:
    def __init__(self):
        self.globals = {}
        self.tools = {}
        self._setup_environment()
        self._setup_tools()
        self._setup_ai_assistant()
    
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
        self.globals.update({
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
            'print': print,
            'range': range,
            'repr': repr,
            'reversed': reversed,
            'set': set,
            'sorted': sorted,
            'str': str,
            'tuple': tuple,
            'type': lambda x: type(x).__name__,
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
        })
        
        for model_type in available_types():
            self.globals[model_type.__name__] = model_type
    
    def _setup_tools(self):
        tools = get_all_tools()
        for tool in tools:
            tool_name = tool.name
            wrapped_tool = self._create_policy_wrapped_tool(tool_name, tool._run)
            self.tools[tool_name] = wrapped_tool
            self.globals[tool_name] = wrapped_tool
        
        self.globals['query_ai_assistant'] = self._query_ai_assistant
    
    def _create_policy_wrapped_tool(self, tool_name: str, original_tool_func):
        """Create a wrapper function that validates policies before executing the tool"""
        def policy_validated_tool(*args, **kwargs):
            additional_context = {}
            
            if tool_name in ["delete_file", "share_file"] and "file_id" in kwargs:
                file_id = kwargs["file_id"]
                try:
                    from tools import file_store
                    for file in file_store.files:
                        if file.id_ == file_id:
                            additional_context["file_content"] = file.content
                            break
                except Exception:
                    pass
            
            is_allowed, violations = policy_engine.evaluate_tool_call(
                tool_name, kwargs, additional_context
            )
            
            if not is_allowed:
                violation_msg = f"Policy violation for {tool_name}: " + "; ".join(violations)
                raise PolicyViolationError(violation_msg, violations)
            
            return original_tool_func(*args, **kwargs)
        
        return policy_validated_tool
    
    def _query_ai_assistant(self, query: str, output_schema: Type[BaseModel]) -> BaseModel:
        model_with_structure = self.llm.with_structured_output(output_schema)
        
        result = model_with_structure.invoke(query)
        return result
    
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
            return node.value
        
        elif isinstance(node, ast.Num):
            return node.n
        
        elif isinstance(node, ast.Str):
            return node.s
        
        elif isinstance(node, ast.List):
            result = []
            for elem in node.elts:
                if isinstance(elem, ast.Starred):
                    # Unpack starred expression: [*list1, item, *list2]
                    starred_value = self._execute_node(elem.value)
                    if hasattr(starred_value, '__iter__') and not isinstance(starred_value, (str, bytes)):
                        result.extend(starred_value)
                    else:
                        raise TypeError(f"'{type(starred_value).__name__}' object is not iterable")
                else:
                    result.append(self._execute_node(elem))
            return result
        
        elif isinstance(node, ast.Tuple):
            result = []
            for elem in node.elts:
                if isinstance(elem, ast.Starred):
                    # Unpack starred expression: (*tuple1, item, *tuple2)
                    starred_value = self._execute_node(elem.value)
                    if hasattr(starred_value, '__iter__') and not isinstance(starred_value, (str, bytes)):
                        result.extend(starred_value)
                    else:
                        raise TypeError(f"'{type(starred_value).__name__}' object is not iterable")
                else:
                    result.append(self._execute_node(elem))
            return tuple(result)
        
        elif isinstance(node, ast.Starred):
            # This handles starred expressions in other contexts
            # The actual unpacking logic is handled by the parent node (List, Tuple, Call)
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.Dict):
            keys = [self._execute_node(k) if k else None for k in node.keys]
            values = [self._execute_node(v) for v in node.values]
            return dict(zip(keys, values))
        
        elif isinstance(node, ast.Set):
            result = set()
            for elem in node.elts:
                if isinstance(elem, ast.Starred):
                    # Unpack starred expression: {*set1, item, *set2}
                    starred_value = self._execute_node(elem.value)
                    if hasattr(starred_value, '__iter__') and not isinstance(starred_value, (str, bytes)):
                        result.update(starred_value)
                    else:
                        raise TypeError(f"'{type(starred_value).__name__}' object is not iterable")
                else:
                    result.add(self._execute_node(elem))
            return result
        
        elif isinstance(node, ast.Call):
            func = self._execute_node(node.func)
            args = []
            
            # Handle regular and starred arguments
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    # Unpack starred argument: func(*args)
                    starred_value = self._execute_node(arg.value)
                    if hasattr(starred_value, '__iter__') and not isinstance(starred_value, (str, bytes)):
                        args.extend(starred_value)
                    else:
                        raise TypeError(f"'{type(starred_value).__name__}' object is not iterable")
                else:
                    args.append(self._execute_node(arg))
            
            kwargs = {kw.arg: self._execute_node(kw.value) for kw in node.keywords}
            
            if callable(func):
                return func(*args, **kwargs)
            else:
                raise TypeError(f"'{type(func).__name__}' object is not callable")
        
        elif isinstance(node, ast.Attribute):
            obj = self._execute_node(node.value)
            return getattr(obj, node.attr)
        
        elif isinstance(node, ast.Subscript):
            obj = self._execute_node(node.value)
            key = self._execute_node(node.slice)
            return obj[key]
        
        elif isinstance(node, ast.Index):
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.Slice):
            lower = self._execute_node(node.lower) if node.lower else None
            upper = self._execute_node(node.upper) if node.upper else None
            step = self._execute_node(node.step) if node.step else None
            return slice(lower, upper, step)
        
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
            
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
            elif isinstance(node.op, ast.FloorDiv):
                return left // right
            elif isinstance(node.op, ast.Mod):
                return left % right
            elif isinstance(node.op, ast.Pow):
                return left ** right
            elif isinstance(node.op, ast.LShift):
                return left << right
            elif isinstance(node.op, ast.RShift):
                return left >> right
            elif isinstance(node.op, ast.BitOr):
                return left | right
            elif isinstance(node.op, ast.BitXor):
                return left ^ right
            elif isinstance(node.op, ast.BitAnd):
                return left & right
        
        elif isinstance(node, ast.UnaryOp):
            operand = self._execute_node(node.operand)
            
            if isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.Not):
                return not operand
            elif isinstance(node.op, ast.Invert):
                return ~operand
        
        elif isinstance(node, ast.Compare):
            left = self._execute_node(node.left)
            result = True
            
            for op, comparator in zip(node.ops, node.comparators):
                right = self._execute_node(comparator)
                
                if isinstance(op, ast.Eq):
                    result = left == right
                elif isinstance(op, ast.NotEq):
                    result = left != right
                elif isinstance(op, ast.Lt):
                    result = left < right
                elif isinstance(op, ast.LtE):
                    result = left <= right
                elif isinstance(op, ast.Gt):
                    result = left > right
                elif isinstance(op, ast.GtE):
                    result = left >= right
                elif isinstance(op, ast.Is):
                    result = left is right
                elif isinstance(op, ast.IsNot):
                    result = left is not right
                elif isinstance(op, ast.In):
                    result = left in right
                elif isinstance(op, ast.NotIn):
                    result = left not in right
                
                if not result:
                    break
                left = right
            
            return result
        
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    result = self._execute_node(value)
                    if not result:
                        return result
                return result
            elif isinstance(node.op, ast.Or):
                for value in node.values:
                    result = self._execute_node(value)
                    if result:
                        return result
                return result
        
        elif isinstance(node, ast.If):
            test = self._execute_node(node.test)
            if test:
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
            result = None
            
            for item in iter_obj:
                self._assign_target(target, item)
                result = None
                for stmt in node.body:
                    result = self._execute_node(stmt)
            
            return result
        
        elif isinstance(node, ast.While):
            result = None
            while self._execute_node(node.test):
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
            
            class_dict = {'__module__': '__main__'}
            annotations = {}
            
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    field_name = stmt.target.id
                    field_type = self._execute_node(stmt.annotation)
                    annotations[field_name] = field_type
                    if stmt.value:
                        default_value = self._execute_node(stmt.value)
                        class_dict[field_name] = default_value
            
            class_dict['__annotations__'] = annotations
            
            new_class = type(class_name, tuple(bases), class_dict)
            self.globals[class_name] = new_class
            return new_class
        
        elif isinstance(node, ast.AnnAssign):
            return None
        
        elif isinstance(node, ast.JoinedStr):
            result = ""
            for value in node.values:
                if isinstance(value, ast.Str):
                    result += value.s
                elif isinstance(value, ast.Constant):
                    result += str(value.value)
                elif isinstance(value, ast.FormattedValue):
                    val = self._execute_node(value.value)
                    if value.format_spec:
                        format_spec = self._execute_node(value.format_spec)
                        result += format(val, format_spec)
                    else:
                        result += str(val)
            return result
        
        elif isinstance(node, ast.FormattedValue):
            return self._execute_node(node.value)
        
        elif isinstance(node, ast.ListComp):
            result = []
            
            def process_generators(generators, generator_index=0):
                if generator_index >= len(generators):
                    element = self._execute_node(node.elt)
                    result.append(element)
                    return
                
                generator = generators[generator_index]
                
                for iter_value in self._execute_node(generator.iter):
                    old_globals = self.globals.copy()
                    try:
                        self._assign_target(generator.target, iter_value)
                        should_continue = True
                        for if_clause in generator.ifs:
                            if not self._execute_node(if_clause):
                                should_continue = False
                                break
                        
                        if should_continue:
                            process_generators(generators, generator_index + 1)
                    finally:
                        self.globals = old_globals
            
            process_generators(node.generators)
            return result
        
        else:
            raise NotImplementedError(f"Node type {type(node).__name__} not implemented")

    def _assign_target(self, target: ast.AST, value: Any) -> None:
        """Handle assignment to various target types including tuple unpacking"""
        if isinstance(target, ast.Name):
            self.globals[target.id] = value
        
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            # Tuple/list unpacking: a, b, c = (1, 2, 3) or a, *rest, b = some_list
            if not hasattr(value, '__iter__') or isinstance(value, (str, bytes)):
                raise TypeError(f"cannot unpack non-sequence {type(value).__name__}")
            
            try:
                values = list(value)
            except TypeError:
                raise TypeError(f"'{type(value).__name__}' object is not iterable")
            
            # Check for starred expressions
            starred_indices = []
            for i, target_elem in enumerate(target.elts):
                if isinstance(target_elem, ast.Starred):
                    starred_indices.append(i)
            
            if len(starred_indices) > 1:
                raise SyntaxError("multiple starred expressions in assignment")
            elif len(starred_indices) == 1:
                # handle starred unpacking: a, *rest, b = values
                starred_index = starred_indices[0]
                non_starred_count = len(target.elts) - 1  # all except the starred one
                
                if len(values) < non_starred_count:
                    raise ValueError(f"not enough values to unpack (expected at least {non_starred_count}, got {len(values)})")
                
                # assign values before the starred expression
                for i in range(starred_index):
                    self._assign_target(target.elts[i], values[i])
                
                # assign the starred expression (gets the middle values)
                starred_target = target.elts[starred_index]
                if isinstance(starred_target, ast.Starred):
                    remaining_after_star = len(target.elts) - starred_index - 1
                    star_values = values[starred_index:len(values) - remaining_after_star] if remaining_after_star > 0 else values[starred_index:]
                    self._assign_target(starred_target.value, star_values)
                
                # Assign values after the starred expression
                remaining_targets = len(target.elts) - starred_index - 1
                for i in range(remaining_targets):
                    target_idx = starred_index + 1 + i
                    value_idx = len(values) - remaining_targets + i
                    self._assign_target(target.elts[target_idx], values[value_idx])
            else:
                # Regular unpacking without starred expressions
                if len(target.elts) != len(values):
                    raise ValueError(f"too many values to unpack (expected {len(target.elts)})")
                
                for target_elem, val in zip(target.elts, values):
                    self._assign_target(target_elem, val)
        
        elif isinstance(target, ast.Subscript):
            obj = self._execute_node(target.value)
            key = self._execute_node(target.slice)
            obj[key] = value
        
        elif isinstance(target, ast.Attribute):
            obj = self._execute_node(target.value)
            setattr(obj, target.attr, value)
        
        else:
            raise NotImplementedError(f"Assignment to {type(target).__name__} not implemented")


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