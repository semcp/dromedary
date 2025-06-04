import matplotlib

# use interactive backend
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
import networkx as nx
from typing import Dict, Any, Set, List
from capability import CapabilityValue, Source, SourceType


class DependencyGraphVisualizer:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_labels = {}
        self.node_colors = {}
        self.initial_globals = set()
        
    def set_initial_globals(self, globals_dict: Dict[str, Any]):
        self.initial_globals = set(globals_dict.keys())
        
    def clear_graph(self):
        self.graph.clear()
        self.node_labels.clear()
        self.node_colors.clear()
    
    def build_graph_from_execution_trace(self, interpreter_globals: Dict[str, Any], execution_trace: List[Dict]):
        user_vars = {}
        for var_name, value in interpreter_globals.items():
            if isinstance(value, CapabilityValue) and var_name not in self.initial_globals:
                user_vars[var_name] = value
        
        for var_name, cap_value in user_vars.items():
            self._add_variable_node(var_name, cap_value)
        
        for var_name, cap_value in user_vars.items():
            self._add_variable_dependencies(var_name, cap_value, user_vars)
        
        for call_record in execution_trace:
            self._add_function_call(call_record, user_vars)
    
    def _add_variable_node(self, var_name: str, cap_value: CapabilityValue):
        node_id = f"var_{var_name}"
        if node_id not in self.graph:
            self.graph.add_node(node_id)
            self.node_labels[node_id] = var_name
            self.node_colors[node_id] = self._get_variable_color(cap_value)
    
    def _get_variable_color(self, cap_value: CapabilityValue) -> str:
        if not cap_value.capability.sources:
            return 'gray'
        
        source_type = cap_value.capability.sources[0].type
        if source_type == SourceType.USER:
            return 'green'
        elif source_type == SourceType.TOOL:
            return 'lightblue'
        elif source_type == SourceType.SYSTEM:
            return 'orange'
        return 'gray'
    
    def _add_variable_dependencies(self, var_name: str, cap_value: CapabilityValue, all_vars: Dict[str, CapabilityValue]):
        var_node_id = f"var_{var_name}"
        
        direct_deps = []
        for dep in cap_value.dependencies:
            for dep_var_name, dep_cap_value in all_vars.items():
                if dep is dep_cap_value:
                    direct_deps.append(dep_var_name)
                    break
        
        # filter out indirect dependencies. If A->B->C, we only want to show B->C, not A->C
        filtered_deps = []
        for dep_var_name in direct_deps:
            is_indirect = False
            dep_cap_value = all_vars[dep_var_name]
            
            for other_dep_name in direct_deps:
                if other_dep_name != dep_var_name:
                    other_cap_value = all_vars[other_dep_name]
                    for other_dep in other_cap_value.dependencies:
                        if other_dep is dep_cap_value:
                            is_indirect = True
                            break
                    if is_indirect:
                        break
            
            if not is_indirect:
                filtered_deps.append(dep_var_name)
        
        for dep_var_name in filtered_deps:
            dep_node_id = f"var_{dep_var_name}"
            if not self.graph.has_edge(dep_node_id, var_node_id):
                self.graph.add_edge(dep_node_id, var_node_id)
    
    def _add_function_call(self, call_record: Dict, user_vars: Dict[str, CapabilityValue]):
        """Add function/tool call from execution trace"""
        func_name = call_record['function']
        input_vars = call_record.get('args', [])
        
        for k, v in call_record.get('kwargs', {}).items():
            if isinstance(v, list):
                input_vars.extend(v)
            else:
                input_vars.append(v)
        
        result_var = call_record.get('result_assigned_to')
        
        input_vars = [var for var in input_vars if var in user_vars]
        
        if not input_vars and not result_var:
            # no relevant variables involved
            return
        
        func_node_id = f"func_{func_name}"
        if func_node_id not in self.graph:
            self.graph.add_node(func_node_id)
            self.node_labels[func_node_id] = f"{func_name}()"
            self.node_colors[func_node_id] = 'blue'
        
        for var_name in input_vars:
            var_node_id = f"var_{var_name}"
            if not self.graph.has_edge(var_node_id, func_node_id):
                self.graph.add_edge(var_node_id, func_node_id)
        
        if result_var and result_var in user_vars:
            var_node_id = f"var_{result_var}"
            if not self.graph.has_edge(func_node_id, var_node_id):
                self.graph.add_edge(func_node_id, var_node_id)
    
    def show_interactive_visualization(self) -> str:
        """Show the interactive dependency graph"""
        if len(self.graph.nodes) == 0:
            print("❌ No dependency graph to visualize")
            return "No dependency graph to visualize"
        
        plt.figure(figsize=(16, 10))
        plt.clf()
        
        if len(self.graph.nodes) <= 15:
            pos = self._create_hierarchical_layout()
        else:
            pos = nx.spring_layout(self.graph, k=3.0, iterations=150, seed=42)
        
        node_colors = [self.node_colors.get(node, 'gray') for node in self.graph.nodes()]
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, node_size=1200, alpha=0.8)
        
        nx.draw_networkx_edges(self.graph, pos, arrows=True, arrowsize=25, alpha=0.7, 
                             edge_color='darkgray', width=2, arrowstyle='->')
        
        nx.draw_networkx_labels(self.graph, pos, self.node_labels, font_size=10, font_weight='bold')
        
        plt.title('Dromedary Data and Control Flow Graph', fontsize=16, fontweight='bold', pad=20)
        plt.axis('off')
        
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=12, label='User Data'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=12, label='Function/Tool'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightblue', markersize=12, label='Tool Result'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=12, label='System Operation'),
        ]
        plt.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        plt.tight_layout()
        plt.show()
        
        return "Interactive visualization displayed"
    
    def _create_hierarchical_layout(self) -> Dict:
        """Create a left-to-right hierarchical layout"""
        pos = {}
        
        sources = [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0]
        
        if not sources:
            return nx.spring_layout(self.graph, k=3.0, iterations=150, seed=42)
        
        levels = {}
        for node in self.graph.nodes():
            min_level = float('inf')
            for source in sources:
                try:
                    path_length = nx.shortest_path_length(self.graph, source, node)
                    min_level = min(min_level, path_length)
                except nx.NetworkXNoPath:
                    continue
            levels[node] = min_level if min_level != float('inf') else 0
        
        level_groups = {}
        for node, level in levels.items():
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(node)
        
        x_spacing = 4.0
        y_spacing = 2.0
        
        for level, nodes in level_groups.items():
            x = level * x_spacing
            y_start = -(len(nodes) - 1) * y_spacing / 2
            
            for i, node in enumerate(nodes):
                y = y_start + i * y_spacing
                pos[node] = (x, y)
        
        return pos


class InterpreterVisualized:
    def __init__(self, interpreter_class, **interpreter_kwargs):
        self.interpreter = interpreter_class(**interpreter_kwargs)
        self.visualizer = DependencyGraphVisualizer()

        self.visualizer.set_initial_globals(self.interpreter.globals)
    
    def clear_for_new_conversation(self):
        """Clear the dependency graph and execution trace for a new conversation"""
        self.visualizer.clear_graph()
        if hasattr(self.interpreter, 'clear_execution_trace'):
            self.interpreter.clear_execution_trace()
        if hasattr(self.interpreter, 'reset_globals'):
            self.interpreter.reset_globals()
            self.visualizer.set_initial_globals(self.interpreter.globals)
        
        plt.close('all')
    
    def execute(self, code: str) -> Dict[str, Any]:
        self.visualizer.clear_graph()
        
        if hasattr(self.interpreter, 'clear_execution_trace'):
            self.interpreter.clear_execution_trace()
        
        result = self.interpreter.execute(code)
        
        if result["success"]:
            execution_trace = self.interpreter.get_execution_trace() if hasattr(self.interpreter, 'get_execution_trace') else []
            self.visualizer.build_graph_from_execution_trace(self.interpreter.globals, execution_trace)
        
        return result
    
    def visualize(self) -> str:
        return self.visualizer.show_interactive_visualization()
