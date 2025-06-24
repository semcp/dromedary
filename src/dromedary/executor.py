import ast
import operator
from typing import Any, Dict, List, Union
from dataclasses import dataclass

from .provenance_graph import CapabilityValue, ProvenanceTracker, Source, SourceType


@dataclass
class MethodReference:
    """Represents a method reference without creating a provenance node."""
    parent_cap: CapabilityValue
    attr_name: str


class NodeExecutor(ast.NodeVisitor):
    """AST Node executor using the Visitor pattern for better separation of concerns."""
    
    def __init__(self, globals_dict: Dict[str, Any], provenance_tracker: ProvenanceTracker):
        self.globals = globals_dict
        self.provenance = provenance_tracker
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
                starred_cap = self.visit(elem.value)
                dependencies.append(starred_cap)
                
                if hasattr(starred_cap.value, '__iter__') and not isinstance(starred_cap.value, (str, bytes)):
                    result.extend(starred_cap.value)
                else:
                    raise TypeError(f"'{type(starred_cap.value).__name__}' object is not iterable")
            else:
                elem_cap = self.visit(elem)
                result.append(elem_cap.value)
                dependencies.append(elem_cap)
        
        return result, dependencies
    
    def _process_sequence_elements_for_set(self, elements: List[ast.AST]) -> tuple[set, List[CapabilityValue]]:
        """Process a sequence of AST elements for set construction, handling starred expressions."""
        result = set()
        dependencies = []
        
        for elem in elements:
            if isinstance(elem, ast.Starred):
                starred_cap = self.visit(elem.value)
                dependencies.append(starred_cap)
                
                if hasattr(starred_cap.value, '__iter__') and not isinstance(starred_cap.value, (str, bytes)):
                    result.update(starred_cap.value)
                else:
                    raise TypeError(f"'{type(starred_cap.value).__name__}' object is not iterable")
            else:
                elem_cap = self.visit(elem)
                result.add(elem_cap.value)
                dependencies.append(elem_cap)
        
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
                key_cap = self.visit(k)
                keys.append(key_cap.value)
                dependencies.append(key_cap)
            else:
                keys.append(None)
            
            val_cap = self.visit(v)
            values.append(val_cap.value)
            dependencies.append(val_cap)
        
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
    
    def _process_call_args(self, node: ast.Call) -> tuple[list, list, dict, dict, list]:
        """Process function call arguments and return args, unwrapped_args, kwargs, unwrapped_kwargs, dependencies."""
        args = []
        unwrapped_args = []
        dependencies = []
        
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                starred_cap = self.visit(arg.value)
                dependencies.append(starred_cap)
                
                if hasattr(starred_cap.value, '__iter__') and not isinstance(starred_cap.value, (str, bytes)):
                    unwrapped_args.extend(starred_cap.value)
                else:
                    raise TypeError(f"'{type(starred_cap.value).__name__}' object is not iterable")
            else:
                arg_cap = self.visit(arg)
                args.append(arg_cap)
                unwrapped_args.append(arg_cap.value)
                dependencies.append(arg_cap)
        
        kwargs = {}
        unwrapped_kwargs = {}
        for kw in node.keywords:
            kw_cap = self.visit(kw.value)
            kwargs[kw.arg] = kw_cap
            unwrapped_kwargs[kw.arg] = kw_cap.value
            dependencies.append(kw_cap)
        
        return args, unwrapped_args, kwargs, unwrapped_kwargs, dependencies

    def visit_Call(self, node: ast.Call) -> CapabilityValue:
        func_or_method_ref = self.visit(node.func)
        args, unwrapped_args, kwargs, unwrapped_kwargs, arg_dependencies = self._process_call_args(node)

        all_input_dependencies = []
        
        if isinstance(func_or_method_ref, MethodReference):
            parent_cap = func_or_method_ref.parent_cap
            func = getattr(parent_cap.value, func_or_method_ref.attr_name)
            func_name = func_or_method_ref.attr_name
            all_input_dependencies.append(parent_cap)
        else:
            func_cap = func_or_method_ref
            func = func_cap.value
            func_name = getattr(func, '__name__', 'call')
            if hasattr(node.func, 'id'):
                func_name = node.func.id
            elif hasattr(node.func, 'attr'):
                func_name = node.func.attr
            all_input_dependencies.append(func_cap)
            
        all_input_dependencies.extend(arg_dependencies)

        invocation_source = Source(type=SourceType.INVOCATION, identifier=func_name)
        invocation_node_id = self.provenance.graph.add_node(
            func_name, 
            invocation_source, 
            dependency_ids=[dep.node_id for dep in all_input_dependencies]
        )
        invocation_cap = CapabilityValue(node_id=invocation_node_id, value=func_name)
        
        if func_name:
            self._record_function_call(func_name, args, kwargs)
        
        if callable(func):
            if self._is_special_function(func):
                # Pass the invocation node as a dependency to the special function.
                # The wrappers in interpreter.py are designed to accept this.
                kwargs['dependencies'] = [invocation_cap]
                
                result = func(*args, **kwargs)

                if not isinstance(result, CapabilityValue):
                    raise TypeError(f"Special function {func_name} was expected to return a CapabilityValue.")
                
                # The special function now returns a correctly linked CapabilityValue.
                return result
            else:
                # This is a standard function returning a raw value. Wrap it and link
                # it to the invocation node.
                result_value = func(*unwrapped_args, **unwrapped_kwargs)
                return self.provenance.from_computation(result_value, dependencies=[invocation_cap])
        else:
            raise TypeError(f"'{type(func).__name__}' object is not callable")
    
    def visit_Attribute(self, node: ast.Attribute) -> Union[CapabilityValue, MethodReference]:
        obj_cap = self.visit(node.value)
        result = getattr(obj_cap.value, node.attr)
        
        if callable(result):
            return MethodReference(parent_cap=obj_cap, attr_name=node.attr)
        else:
            dependencies = [obj_cap]
            return self.provenance.from_computation(result, dependencies)
    
    def visit_Subscript(self, node: ast.Subscript) -> CapabilityValue:
        obj_cap = self.visit(node.value)
        key_cap = self.visit(node.slice)
        
        result = obj_cap.value[key_cap.value]
        
        dependencies = [obj_cap, key_cap]
        return self.provenance.from_computation(result, dependencies)
    
    def visit_Index(self, node: ast.Index) -> Any:
        return self.visit(node.value)
    
    def visit_Slice(self, node: ast.Slice) -> CapabilityValue:
        dependencies = []
        
        lower = None
        if node.lower:
            lower_cap = self.visit(node.lower)
            lower = lower_cap.value
            dependencies.append(lower_cap)
            
        upper = None
        if node.upper:
            upper_cap = self.visit(node.upper)
            upper = upper_cap.value
            dependencies.append(upper_cap)
            
        step = None
        if node.step:
            step_cap = self.visit(node.step)
            step = step_cap.value
            dependencies.append(step_cap)
        
        result = slice(lower, upper, step)
        return self.provenance.from_computation(result, dependencies)
    
    def visit_IfExp(self, node: ast.IfExp) -> Any:
        test_cap = self.visit(node.test)
        if test_cap.value:
            return self.visit(node.body)
        else:
            return self.visit(node.orelse)
    
    def visit_BinOp(self, node: ast.BinOp) -> CapabilityValue:
        left_cap = self.visit(node.left)
        right_cap = self.visit(node.right)
        
        op_func = self._bin_op_map.get(type(node.op))
        if not op_func:
            raise NotImplementedError(f"Binary operator {type(node.op).__name__} not implemented")
        
        result_val = op_func(left_cap.value, right_cap.value)
        
        dependencies = [left_cap, right_cap]
        return self.provenance.from_computation(result_val, dependencies)
    
    def visit_UnaryOp(self, node: ast.UnaryOp) -> CapabilityValue:
        operand_cap = self.visit(node.operand)
        
        op_func = self._unary_op_map.get(type(node.op))
        if not op_func:
            raise NotImplementedError(f"Unary operator {type(node.op).__name__} not implemented")
        
        result_val = op_func(operand_cap.value)
        dependencies = [operand_cap]
        
        return self.provenance.from_computation(result_val, dependencies)
    
    def visit_Compare(self, node: ast.Compare) -> CapabilityValue:
        left_cap = self.visit(node.left)
        current_val = left_cap.value
        result = True
        dependencies = [left_cap]
        
        for op, comparator in zip(node.ops, node.comparators):
            right_cap = self.visit(comparator)
            dependencies.append(right_cap)
            
            op_func = self._compare_op_map.get(type(op))
            if not op_func:
                raise NotImplementedError(f"Comparison operator {type(op).__name__} not implemented")
            
            result = op_func(current_val, right_cap.value)
            
            if not result:
                break
            current_val = right_cap.value
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_BoolOp(self, node: ast.BoolOp) -> CapabilityValue:
        dependencies = []
        
        if isinstance(node.op, ast.And):
            for value in node.values:
                result_cap = self.visit(value)
                dependencies.append(result_cap)
                if not result_cap.value:
                    return self.provenance.from_computation(result_cap.value, dependencies)
            return self.provenance.from_computation(result_cap.value, dependencies)
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                result_cap = self.visit(value)
                dependencies.append(result_cap)
                if result_cap.value:
                    return self.provenance.from_computation(result_cap.value, dependencies)
            return self.provenance.from_computation(result_cap.value, dependencies)
    
    def visit_If(self, node: ast.If) -> Any:
        test_cap = self.visit(node.test)
        
        if test_cap.value:
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
        iter_cap = self.visit(node.iter)
        result = None
        
        for item in iter_cap.value:
            item_cap = self.provenance.from_computation(item, [iter_cap])
            self._assign_target(node.target, item_cap)
            result = None
            for stmt in node.body:
                result = self.visit(stmt)
        
        return result
    
    def visit_While(self, node: ast.While) -> Any:
        result = None
        while True:
            test_cap = self.visit(node.test)
            if not test_cap.value:
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
        if not module_name:
            return None
            
        try:
            # Dynamically import the module
            import importlib
            module = importlib.import_module(module_name)
            
            for alias in node.names:
                import_name = alias.name
                as_name = alias.asname or import_name
                
                if hasattr(module, import_name):
                    # Get the actual object from the module
                    imported_obj = getattr(module, import_name)
                    # Wrap it in a CapabilityValue with proper provenance tracking
                    self.globals[as_name] = self.provenance.from_system(imported_obj, f"import.{module_name}")
                else:
                    raise ImportError(f"cannot import name '{import_name}' from '{module_name}'")
                    
        except ImportError as e:
            raise ImportError(f"No module named '{module_name}' or {str(e)}")
        
        return None
    
    def visit_ClassDef(self, node: ast.ClassDef) -> CapabilityValue:
        class_name = node.name
        base_caps = [self.visit(base) for base in node.bases]
        unwrapped_bases = [base_cap.value for base_cap in base_caps]
        
        class_dict = {'__module__': '__main__'}
        annotations = {}
        dependencies = base_caps.copy()
        
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                field_name = stmt.target.id
                field_type_cap = self.visit(stmt.annotation)
                annotations[field_name] = field_type_cap.value
                dependencies.append(field_type_cap)
                
                if stmt.value:
                    default_value_cap = self.visit(stmt.value)
                    class_dict[field_name] = default_value_cap.value
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
                dependencies.append(val_cap)
                
                if value.format_spec:
                    format_spec_cap = self.visit(value.format_spec)
                    dependencies.append(format_spec_cap)
                    result += format(val_cap.value, format_spec_cap.value)
                else:
                    result += str(val_cap.value)
        
        return self.provenance.from_computation(result, dependencies)
    
    def visit_FormattedValue(self, node: ast.FormattedValue) -> Any:
        return self.visit(node.value)
    
    def visit_ListComp(self, node: ast.ListComp) -> CapabilityValue:
        result = []
        dependencies = []
        
        def process_generators(generators, generator_index=0):
            if generator_index >= len(generators):
                element_cap = self.visit(node.elt)
                result.append(element_cap.value)
                dependencies.append(element_cap)
                return
            
            generator = generators[generator_index]
            iter_cap = self.visit(generator.iter)
            dependencies.append(iter_cap)
            
            for iter_value in iter_cap.value:
                old_globals = self.globals.copy()
                try:
                    iter_cap_value = self.provenance.from_computation(iter_value, [iter_cap])
                    self._assign_target(generator.target, iter_cap_value)
                    should_continue = True
                    for if_clause in generator.ifs:
                        if_cap = self.visit(if_clause)
                        dependencies.append(if_cap)
                        if not if_cap.value:
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
            if not hasattr(value.value, '__iter__') or isinstance(value.value, (str, bytes)):
                raise TypeError(f"cannot unpack non-sequence {type(value.value).__name__}")
            
            try:
                values = list(value.value)
            except TypeError:
                raise TypeError(f"'{type(value.value).__name__}' object is not iterable")
            
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
                    item_cap = self.provenance.from_computation(values[i], [value])
                    self._assign_target(target.elts[i], item_cap)
                
                starred_target = target.elts[starred_index]
                if isinstance(starred_target, ast.Starred):
                    remaining_after_star = len(target.elts) - starred_index - 1
                    star_values = values[starred_index:len(values) - remaining_after_star] if remaining_after_star > 0 else values[starred_index:]
                    star_cap = self.provenance.from_computation(star_values, [value])
                    self._assign_target(starred_target.value, star_cap)
                
                remaining_targets = len(target.elts) - starred_index - 1
                for i in range(remaining_targets):
                    target_idx = starred_index + 1 + i
                    value_idx = len(values) - remaining_targets + i
                    item_cap = self.provenance.from_computation(values[value_idx], [value])
                    self._assign_target(target.elts[target_idx], item_cap)
            else:
                if len(target.elts) != len(values):
                    raise ValueError(f"too many values to unpack (expected {len(target.elts)})")
                
                for target_elem, val in zip(target.elts, values):
                    val_cap = self.provenance.from_computation(val, [value])
                    self._assign_target(target_elem, val_cap)
        
        elif isinstance(target, ast.Subscript):
            obj_cap = self.visit(target.value)
            key_cap = self.visit(target.slice)
            
            try:
                if key_cap.value is not None:
                    hash(key_cap.value)
                obj_cap.value[key_cap.value] = value.value
            except TypeError:
                raise
        
        elif isinstance(target, ast.Attribute):
            obj_cap = self.visit(target.value)
            setattr(obj_cap.value, target.attr, value.value)
        
        else:
            raise NotImplementedError(f"Assignment to {type(target).__name__} not implemented")
    
    def _is_special_function(self, func: Any) -> bool:
        """Check if this function needs CapabilityValues instead of unwrapped values."""
        # This will be set by the interpreter based on tools and AI assistant
        return hasattr(func, '_needs_capability_values') and func._needs_capability_values
    
    def _record_function_call(self, func_name: str, args: list, kwargs: dict, result_var: str = None):
        """Record function calls with values and their CapabilityValue wrappers."""
        arg_values = [arg.value if isinstance(arg, CapabilityValue) else arg for arg in args]
        kwarg_values = {k: v.value if isinstance(v, CapabilityValue) else v for k, v in kwargs.items()}
        
        call_record = {
            'function': func_name,
            'args': arg_values,
            'kwargs': kwarg_values,
            'result_assigned_to': result_var
        }
        self.execution_trace.append(call_record)
        return call_record 