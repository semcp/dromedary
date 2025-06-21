import ast
import operator
from datetime import datetime, timedelta, date, time, timezone
from enum import Enum
from typing import Any, Dict, List, Union, Optional
from pydantic import BaseModel, Field, EmailStr

from .capability import CapabilityValue
from .provenance import ProvenanceManager


class NodeExecutor(ast.NodeVisitor):
    """AST Node executor using the Visitor pattern for better separation of concerns."""
    
    def __init__(self, globals_dict: Dict[str, Any], provenance_manager: ProvenanceManager):
        self.globals = globals_dict
        self.provenance = provenance_manager
        self.execution_trace = []
        
        self._bin_op_map = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.LShift: operator.lshift,
            ast.RShift: operator.rshift,
            ast.BitOr: operator.or_,
            ast.BitXor: operator.xor,
            ast.BitAnd: operator.and_,
        }
        
        self._unary_op_map = {
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
            ast.Not: operator.not_,
            ast.Invert: operator.invert,
        }
        
        self._compare_op_map = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.Is: operator.is_,
            ast.IsNot: operator.is_not,
            ast.In: lambda a, b: a in b,
            ast.NotIn: lambda a, b: a not in b,
        }
    
    def _process_sequence_elements(self, elements: List[ast.AST]) -> tuple[List[Any], List[CapabilityValue]]:
        """Process a sequence of AST elements, handling starred expressions."""
        result = []
        dependencies = []
        
        for elem in elements:
            if isinstance(elem, ast.Starred):
                starred_value = self.visit(elem.value)
                starred_unwrapped = self.provenance.unwrap(starred_value)
                dependencies.append(starred_value)
                
                if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                    result.extend(starred_unwrapped)
                else:
                    raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
            else:
                elem_value = self.visit(elem)
                result.append(self.provenance.unwrap(elem_value))
                dependencies.append(elem_value)
        
        return result, dependencies
    
    def _process_sequence_elements_for_set(self, elements: List[ast.AST]) -> tuple[set, List[CapabilityValue]]:
        """Process a sequence of AST elements for set construction, handling starred expressions."""
        result = set()
        dependencies = []
        
        for elem in elements:
            if isinstance(elem, ast.Starred):
                starred_value = self.visit(elem.value)
                starred_unwrapped = self.provenance.unwrap(starred_value)
                dependencies.append(starred_value)
                
                if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                    result.update(starred_unwrapped)
                else:
                    raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
            else:
                elem_value = self.visit(elem)
                result.add(self.provenance.unwrap(elem_value))
                dependencies.append(elem_value)
        
        return result, dependencies
    
    def visit(self, node):
        """Override to handle the result properly."""
        method = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)
    
    def visit_Module(self, node: ast.Module) -> Any:
        result = None
        for child in node.body:
            result = self.visit(child)
        return result
    
    def visit_Expr(self, node: ast.Expr) -> Any:
        return self.visit(node.value)
    
    def visit_Assign(self, node: ast.Assign) -> Any:
        value = self.visit(node.value)
        for target in node.targets:
            self._assign_target(target, value)
        return value
    
    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self.globals:
            return self.globals[node.id]
        raise NameError(f"name '{node.id}' is not defined")
    
    def visit_Constant(self, node: ast.Constant) -> CapabilityValue:
        return self.provenance.literal(node.value)
    
    def visit_Num(self, node: ast.Num) -> CapabilityValue:
        return self.provenance.literal(node.n)
    
    def visit_Str(self, node: ast.Str) -> CapabilityValue:
        return self.provenance.literal(node.s)
    
    def visit_List(self, node: ast.List) -> CapabilityValue:
        result, dependencies = self._process_sequence_elements(node.elts)
        return self.provenance.from_computation(result, dependencies)
    
    def visit_Tuple(self, node: ast.Tuple) -> CapabilityValue:
        result, dependencies = self._process_sequence_elements(node.elts)
        return self.provenance.from_computation(tuple(result), dependencies)
    
    def visit_Starred(self, node: ast.Starred) -> Any:
        return self.visit(node.value)
    
    def visit_Dict(self, node: ast.Dict) -> CapabilityValue:
        keys = []
        values = []
        dependencies = []
        
        for k, v in zip(node.keys, node.values):
            if k:
                key_value = self.visit(k)
                unwrapped_key = self.provenance.unwrap(key_value)
                keys.append(unwrapped_key)
                dependencies.append(key_value)
            else:
                keys.append(None)
            
            val_value = self.visit(v)
            values.append(self.provenance.unwrap(val_value))
            dependencies.append(val_value)
        
        # Validate that all keys are hashable before creating the dictionary
        try:
            result_dict = {}
            for key, value in zip(keys, values):
                if key is not None:
                    # Test if the key is hashable by attempting to hash it
                    hash(key)
                result_dict[key] = value
        except TypeError as e:
            if "unhashable type" in str(e):
                # Provide a more descriptive error message
                unhashable_keys = []
                for key in keys:
                    if key is not None:
                        try:
                            hash(key)
                        except TypeError:
                            unhashable_keys.append(f"{type(key).__name__}: {repr(key)}")
                
                if unhashable_keys:
                    raise TypeError(f"Dictionary keys must be hashable. Found unhashable keys: {', '.join(unhashable_keys)}")
            raise  # Re-raise the original error if it's not about unhashable types
        
        return self.provenance.from_computation(result_dict, dependencies)
    
    def visit_Set(self, node: ast.Set) -> CapabilityValue:
        result, dependencies = self._process_sequence_elements_for_set(node.elts)
        return self.provenance.from_computation(result, dependencies)
    
    def visit_Call(self, node: ast.Call) -> CapabilityValue:
        func = self.visit(node.func)
        unwrapped_func = self.provenance.unwrap(func)
        args = []
        unwrapped_args = []
        dependencies = [func] if isinstance(func, CapabilityValue) else []
        
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                starred_value = self.visit(arg.value)
                starred_unwrapped = self.provenance.unwrap(starred_value)
                dependencies.append(starred_value)
                
                if hasattr(starred_unwrapped, '__iter__') and not isinstance(starred_unwrapped, (str, bytes)):
                    unwrapped_args.extend(starred_unwrapped)
                else:
                    raise TypeError(f"'{type(starred_unwrapped).__name__}' object is not iterable")
            else:
                arg_value = self.visit(arg)
                args.append(arg_value)
                unwrapped_args.append(self.provenance.unwrap(arg_value))
                dependencies.append(arg_value)
        
        kwargs = {}
        unwrapped_kwargs = {}
        for kw in node.keywords:
            kw_value = self.visit(kw.value)
            kwargs[kw.arg] = kw_value
            unwrapped_kwargs[kw.arg] = self.provenance.unwrap(kw_value)
            dependencies.append(kw_value)
        
        func_name = None
        if hasattr(node.func, 'id'):
            func_name = node.func.id
        elif hasattr(node.func, 'attr'):
            func_name = node.func.attr
        
        if func_name:
            self._record_function_call(func_name, args, kwargs)
        
        if callable(unwrapped_func):
            # Special handling for tools and AI assistant that need CapabilityValues
            if self._is_special_function(unwrapped_func):
                result = unwrapped_func(*args, **kwargs)
            else:
                result = unwrapped_func(*unwrapped_args, **unwrapped_kwargs)
            
            if isinstance(result, CapabilityValue):
                result.dependencies.update({id(dep): dep for dep in dependencies if isinstance(dep, CapabilityValue)})
                return result
            else:
                return self.provenance.from_computation(result, dependencies)
        else:
            raise TypeError(f"'{type(unwrapped_func).__name__}' object is not callable")
    
    def visit_Attribute(self, node: ast.Attribute) -> CapabilityValue:
        obj = self.visit(node.value)
        unwrapped_obj = self.provenance.unwrap(obj)
        result = getattr(unwrapped_obj, node.attr)
        
        dependencies = [obj] if isinstance(obj, CapabilityValue) else []
        return self.provenance.from_computation(result, dependencies)
    
    def visit_Subscript(self, node: ast.Subscript) -> CapabilityValue:
        obj = self.visit(node.value)
        key = self.visit(node.slice)
        unwrapped_obj = self.provenance.unwrap(obj)
        unwrapped_key = self.provenance.unwrap(key)
        
        result = unwrapped_obj[unwrapped_key]
        
        dependencies = []
        if isinstance(obj, CapabilityValue):
            dependencies.append(obj)
        if isinstance(key, CapabilityValue):
            dependencies.append(key)
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_Index(self, node: ast.Index) -> Any:
        return self.visit(node.value)
    
    def visit_Slice(self, node: ast.Slice) -> slice:
        lower = self.visit(node.lower) if node.lower else None
        upper = self.visit(node.upper) if node.upper else None
        step = self.visit(node.step) if node.step else None
        
        lower_unwrapped = self.provenance.unwrap(lower) if lower is not None else None
        upper_unwrapped = self.provenance.unwrap(upper) if upper is not None else None
        step_unwrapped = self.provenance.unwrap(step) if step is not None else None
        
        return slice(lower_unwrapped, upper_unwrapped, step_unwrapped)
    
    def visit_IfExp(self, node: ast.IfExp) -> Any:
        test = self.visit(node.test)
        if test:
            return self.visit(node.body)
        else:
            return self.visit(node.orelse)
    
    def visit_BinOp(self, node: ast.BinOp) -> CapabilityValue:
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        op_func = self._bin_op_map.get(type(node.op))
        if not op_func:
            raise NotImplementedError(f"Binary operator {type(node.op).__name__} not implemented")
        
        result = op_func(self.provenance.unwrap(left), self.provenance.unwrap(right))
        
        dependencies = []
        if isinstance(left, CapabilityValue):
            dependencies.append(left)
        if isinstance(right, CapabilityValue):
            dependencies.append(right)
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_UnaryOp(self, node: ast.UnaryOp) -> CapabilityValue:
        operand = self.visit(node.operand)
        
        op_func = self._unary_op_map.get(type(node.op))
        if not op_func:
            raise NotImplementedError(f"Unary operator {type(node.op).__name__} not implemented")
        
        result = op_func(self.provenance.unwrap(operand))
        dependencies = [operand] if isinstance(operand, CapabilityValue) else []
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_Compare(self, node: ast.Compare) -> CapabilityValue:
        left = self.visit(node.left)
        unwrapped_left = self.provenance.unwrap(left)
        result = True
        dependencies = [left] if isinstance(left, CapabilityValue) else []
        
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            unwrapped_right = self.provenance.unwrap(right)
            
            if isinstance(right, CapabilityValue):
                dependencies.append(right)
            
            op_func = self._compare_op_map.get(type(op))
            if not op_func:
                raise NotImplementedError(f"Comparison operator {type(op).__name__} not implemented")
            
            result = op_func(unwrapped_left, unwrapped_right)
            
            if not result:
                break
            unwrapped_left = unwrapped_right
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_BoolOp(self, node: ast.BoolOp) -> CapabilityValue:
        dependencies = []
        
        if isinstance(node.op, ast.And):
            for value in node.values:
                result_cap = self.visit(value)
                result = self.provenance.unwrap(result_cap)
                if isinstance(result_cap, CapabilityValue):
                    dependencies.append(result_cap)
                if not result:
                    return self.provenance.from_computation(result, dependencies)
            return self.provenance.from_computation(result, dependencies)
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                result_cap = self.visit(value)
                result = self.provenance.unwrap(result_cap)
                if isinstance(result_cap, CapabilityValue):
                    dependencies.append(result_cap)
                if result:
                    return self.provenance.from_computation(result, dependencies)
            return self.provenance.from_computation(result, dependencies)
    
    def visit_If(self, node: ast.If) -> Any:
        test = self.visit(node.test)
        unwrapped_test = self.provenance.unwrap(test)
        
        if unwrapped_test:
            result = None
            for stmt in node.body:
                result = self.visit(stmt)
            return result
        elif node.orelse:
            result = None
            for stmt in node.orelse:
                result = self.visit(stmt)
            return result
    
    def visit_For(self, node: ast.For) -> Any:
        iter_obj = self.visit(node.iter)
        unwrapped_iter = self.provenance.unwrap(iter_obj)
        result = None
        
        for item in unwrapped_iter:
            item_cap = self.provenance.from_computation(item, [iter_obj] if isinstance(iter_obj, CapabilityValue) else [])
            self._assign_target(node.target, item_cap)
            result = None
            for stmt in node.body:
                result = self.visit(stmt)
        
        return result
    
    def visit_While(self, node: ast.While) -> Any:
        result = None
        while True:
            test = self.visit(node.test)
            unwrapped_test = self.provenance.unwrap(test)
            if not unwrapped_test:
                break
            for stmt in node.body:
                result = self.visit(stmt)
        return result
    
    def visit_Return(self, node: ast.Return) -> Any:
        if node.value:
            return self.visit(node.value)
        return None
    
    def visit_Pass(self, node: ast.Pass) -> None:
        return None
    
    def visit_Break(self, node: ast.Break) -> None:
        raise Exception("break")
    
    def visit_Continue(self, node: ast.Continue) -> None:
        raise Exception("continue")
    
    def visit_Import(self, node: ast.Import) -> None:
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
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
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
    
    def visit_ClassDef(self, node: ast.ClassDef) -> CapabilityValue:
        class_name = node.name
        bases = [self.visit(base) for base in node.bases]
        unwrapped_bases = [self.provenance.unwrap(base) for base in bases]
        
        class_dict = {'__module__': '__main__'}
        annotations = {}
        dependencies = []
        
        for base in bases:
            if isinstance(base, CapabilityValue):
                dependencies.append(base)
        
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                field_name = stmt.target.id
                field_type_cap = self.visit(stmt.annotation)
                field_type = self.provenance.unwrap(field_type_cap)
                annotations[field_name] = field_type
                
                if isinstance(field_type_cap, CapabilityValue):
                    dependencies.append(field_type_cap)
                
                if stmt.value:
                    default_value_cap = self.visit(stmt.value)
                    default_value = self.provenance.unwrap(default_value_cap)
                    class_dict[field_name] = default_value
                    
                    if isinstance(default_value_cap, CapabilityValue):
                        dependencies.append(default_value_cap)
        
        class_dict['__annotations__'] = annotations
        
        new_class = type(class_name, tuple(unwrapped_bases), class_dict)
        class_cap_value = self.provenance.from_computation(new_class, dependencies)
        self.globals[class_name] = class_cap_value
        return class_cap_value
    
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        return None
    
    def visit_JoinedStr(self, node: ast.JoinedStr) -> CapabilityValue:
        result = ""
        dependencies = []
        
        for value in node.values:
            if isinstance(value, ast.Str):
                result += value.s
            elif isinstance(value, ast.Constant):
                result += str(value.value)
            elif isinstance(value, ast.FormattedValue):
                val_cap = self.visit(value.value)
                val = self.provenance.unwrap(val_cap)
                if isinstance(val_cap, CapabilityValue):
                    dependencies.append(val_cap)
                
                if value.format_spec:
                    format_spec_cap = self.visit(value.format_spec)
                    format_spec = self.provenance.unwrap(format_spec_cap)
                    if isinstance(format_spec_cap, CapabilityValue):
                        dependencies.append(format_spec_cap)
                    result += format(val, format_spec)
                else:
                    result += str(val)
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_FormattedValue(self, node: ast.FormattedValue) -> Any:
        return self.visit(node.value)
    
    def visit_ListComp(self, node: ast.ListComp) -> CapabilityValue:
        result = []
        dependencies = []
        
        def process_generators(generators, generator_index=0):
            if generator_index >= len(generators):
                element_cap = self.visit(node.elt)
                element = self.provenance.unwrap(element_cap)
                result.append(element)
                if isinstance(element_cap, CapabilityValue):
                    dependencies.append(element_cap)
                return
            
            generator = generators[generator_index]
            iter_cap = self.visit(generator.iter)
            iter_obj = self.provenance.unwrap(iter_cap)
            if isinstance(iter_cap, CapabilityValue):
                dependencies.append(iter_cap)
            
            for iter_value in iter_obj:
                old_globals = self.globals.copy()
                try:
                    iter_cap_value = self.provenance.from_computation(iter_value, [iter_cap] if isinstance(iter_cap, CapabilityValue) else [])
                    self._assign_target(generator.target, iter_cap_value)
                    should_continue = True
                    for if_clause in generator.ifs:
                        if_cap = self.visit(if_clause)
                        if_result = self.provenance.unwrap(if_cap)
                        if isinstance(if_cap, CapabilityValue):
                            dependencies.append(if_cap)
                        if not if_result:
                            should_continue = False
                            break
                    
                    if should_continue:
                        process_generators(generators, generator_index + 1)
                finally:
                    self.globals = old_globals
        
        process_generators(node.generators)
        return self.provenance.from_computation(result, dependencies)
    
    def generic_visit(self, node):
        raise NotImplementedError(f"Node type {type(node).__name__} not implemented")
    
    def _assign_target(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name):
            self.globals[target.id] = value
            
            if self.execution_trace and self.execution_trace[-1]['result_assigned_to'] is None:
                self.execution_trace[-1]['result_assigned_to'] = target.id
        
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            unwrapped_value = self.provenance.unwrap(value)
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
                    item_cap = self.provenance.from_computation(values[i], [value] if isinstance(value, CapabilityValue) else [])
                    self._assign_target(target.elts[i], item_cap)
                
                starred_target = target.elts[starred_index]
                if isinstance(starred_target, ast.Starred):
                    remaining_after_star = len(target.elts) - starred_index - 1
                    star_values = values[starred_index:len(values) - remaining_after_star] if remaining_after_star > 0 else values[starred_index:]
                    star_cap = self.provenance.from_computation(star_values, [value] if isinstance(value, CapabilityValue) else [])
                    self._assign_target(starred_target.value, star_cap)
                
                remaining_targets = len(target.elts) - starred_index - 1
                for i in range(remaining_targets):
                    target_idx = starred_index + 1 + i
                    value_idx = len(values) - remaining_targets + i
                    item_cap = self.provenance.from_computation(values[value_idx], [value] if isinstance(value, CapabilityValue) else [])
                    self._assign_target(target.elts[target_idx], item_cap)
            else:
                if len(target.elts) != len(values):
                    raise ValueError(f"too many values to unpack (expected {len(target.elts)})")
                
                for target_elem, val in zip(target.elts, values):
                    val_cap = self.provenance.from_computation(val, [value] if isinstance(value, CapabilityValue) else [])
                    self._assign_target(target_elem, val_cap)
        
        elif isinstance(target, ast.Subscript):
            obj = self.visit(target.value)
            key = self.visit(target.slice)
            unwrapped_obj = self.provenance.unwrap(obj)
            unwrapped_key = self.provenance.unwrap(key)
            unwrapped_value = self.provenance.unwrap(value)
            
            try:
                if unwrapped_key is not None:
                    hash(unwrapped_key)
                unwrapped_obj[unwrapped_key] = unwrapped_value
            except TypeError:
                raise
        
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            unwrapped_obj = self.provenance.unwrap(obj)
            unwrapped_value = self.provenance.unwrap(value)
            setattr(unwrapped_obj, target.attr, unwrapped_value)
        
        else:
            raise NotImplementedError(f"Assignment to {type(target).__name__} not implemented")
    
    def _is_special_function(self, func: Any) -> bool:
        """Check if this function needs CapabilityValues instead of unwrapped values."""
        # This will be set by the interpreter based on tools and AI assistant
        return hasattr(func, '_needs_capability_values') and func._needs_capability_values
    
    def _record_function_call(self, func_name: str, args: list, kwargs: dict, result_var: str = None):
        """Record function calls with values and their CapabilityValue wrappers."""
        arg_values = [self.provenance.unwrap(arg) if isinstance(arg, CapabilityValue) else arg for arg in args]
        kwarg_values = {k: self.provenance.unwrap(v) if isinstance(v, CapabilityValue) else v for k, v in kwargs.items()}
        
        call_record = {
            'function': func_name,
            'args': arg_values,
            'kwargs': kwarg_values,
            'result_assigned_to': result_var
        }
        self.execution_trace.append(call_record)
        return call_record 