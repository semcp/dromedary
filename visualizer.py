import matplotlib

# use interactive backend
matplotlib.use('MacOSX')

import matplotlib.pyplot as plt
import networkx as nx
from typing import Dict, Any, List
from capability import CapabilityValue, Source, SourceType


class DependencyGraphVisualizer:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_labels = {}
        self.node_colors = {}
        self.initial_globals = set()
        self.topological_order = []
        self.has_cycles = False
        self.cycle_info = []
        
    def set_initial_globals(self, globals_dict: Dict[str, Any]):
        self.initial_globals = set(globals_dict.keys())
        
    def clear_graph(self):
        self.graph.clear()
        self.node_labels.clear()
        self.node_colors.clear()
        self.topological_order.clear()
        self.has_cycles = False
        self.cycle_info.clear()
    
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
            return 'lightgray'
        
        source_type = cap_value.capability.sources[-1].type
        
        if source_type == SourceType.USER:
            return 'lightgreen'
        elif source_type == SourceType.TOOL:
            return 'lightcyan'
        elif source_type == SourceType.SYSTEM:
            return 'lightsalmon'
        
        return 'lightgray'
    
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
            self.node_colors[func_node_id] = 'lightblue'
        
        for var_name in input_vars:
            var_node_id = f"var_{var_name}"
            if not self.graph.has_edge(var_node_id, func_node_id):
                self.graph.add_edge(var_node_id, func_node_id)
        
        if result_var and result_var in user_vars:
            var_node_id = f"var_{result_var}"
            if not self.graph.has_edge(func_node_id, var_node_id):
                self.graph.add_edge(func_node_id, var_node_id)
    
    def _topological_sort(self) -> bool:
        """
        Perform topological sorting on the graph.
        Returns True if the graph is a DAG, False if it has cycles.
        If there are cycles, creates a partial ordering using SCCs.
        """
        try:
            self.topological_order = list(nx.topological_sort(self.graph))
            self.has_cycles = False
            self.cycle_info.clear()
            return True
        except nx.NetworkXError:
            self.has_cycles = True
            
            try:
                cycles = list(nx.simple_cycles(self.graph))
                self.cycle_info = cycles[:5]
            except Exception:
                self.cycle_info = []
            
            self._create_partial_topological_order()
            return False

    def _create_partial_topological_order(self):
        """ Create a partial topological ordering using strongly connected components """
        try:
            sccs = list(nx.strongly_connected_components(self.graph))
            
            condensed_graph = nx.condensation(self.graph, sccs)
            
            scc_topo_order = list(nx.topological_sort(condensed_graph))
            
            self.topological_order = []
            for scc_index in scc_topo_order:
                scc_nodes = sccs[scc_index]
                
                if len(scc_nodes) == 1:
                    self.topological_order.extend(scc_nodes)
                else:
                    subgraph = self.graph.subgraph(scc_nodes)
                    
                    sources_in_scc = [n for n in scc_nodes if subgraph.in_degree(n) == min(subgraph.in_degree(node) for node in scc_nodes)]
                    other_nodes = [n for n in scc_nodes if n not in sources_in_scc]
                    
                    self.topological_order.extend(sources_in_scc)
                    self.topological_order.extend(other_nodes)
        
        except Exception as e:
            print(f"Warning: Could not create partial topological order: {e}")
            self.topological_order = list(self.graph.nodes())

    def _create_topological_layout(self) -> Dict:
        """Create a layout based on topological ordering with proper dependency levels"""
        if not self.topological_order:
            return nx.spring_layout(self.graph, k=3.0, iterations=150, seed=42)
        
        pos = {}
        levels = {}
        
        # assign levels to nodes based on their dependencies
        for node in self.topological_order:
            if self.graph.in_degree(node) == 0:
                levels[node] = 0
            else:
                max_predecessor_level = -1
                for predecessor in self.graph.predecessors(node):
                    if predecessor in levels:
                        max_predecessor_level = max(max_predecessor_level, levels[predecessor])
                levels[node] = max_predecessor_level + 1
        
        # group nodes by their dependency levels
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

    def _create_hierarchical_layout(self) -> Dict:
        """Create a left-to-right hierarchical layout"""
        if self.topological_order:
            return self._create_topological_layout()
        
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

    def show_interactive_visualization(self) -> str:
        """Show the interactive dependency graph"""
        if len(self.graph.nodes) == 0:
            return "No dependency graph to visualize"
        
        is_dag = self._topological_sort()
        
        plt.figure(figsize=(16, 10))
        plt.clf()
        
        if len(self.graph.nodes) <= 15:
            pos = self._create_hierarchical_layout()
        else:
            if is_dag:
                pos = self._create_topological_layout()
            else:
                pos = nx.spring_layout(self.graph, k=3.0, iterations=150, seed=42)
        
        node_colors = [self.node_colors.get(node, 'lightgray') for node in self.graph.nodes()]
        
        if self.has_cycles:
            highlighted_colors = []
            cycle_nodes = set()
            for cycle in self.cycle_info:
                cycle_nodes.update(cycle)
            
            for node in self.graph.nodes():
                if node in cycle_nodes:
                    highlighted_colors.append('red')
                else:
                    highlighted_colors.append(self.node_colors.get(node, 'lightgray'))
            
            node_colors = highlighted_colors
        
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, node_size=3000, alpha=0.9, edgecolors='black', linewidths=1)
        
        edge_colors = []
        edge_widths = []
        for edge in self.graph.edges():
            if self.has_cycles:
                is_cycle_edge = False
                for cycle in self.cycle_info:
                    for i in range(len(cycle)):
                        if (cycle[i] == edge[0] and cycle[(i+1) % len(cycle)] == edge[1]):
                            is_cycle_edge = True
                            break
                    if is_cycle_edge:
                        break
                
                if is_cycle_edge:
                    edge_colors.append('red')
                    edge_widths.append(6)
                else:
                    edge_colors.append('black')
                    edge_widths.append(4)
            else:
                edge_colors.append('black')
                edge_widths.append(4)
        
        nx.draw_networkx_edges(self.graph, pos, arrows=True, arrowsize=25, alpha=0.8, 
                             edge_color=edge_colors, width=edge_widths, arrowstyle='-|>', 
                             connectionstyle='arc3,rad=0.3', min_source_margin=30, min_target_margin=30)
        
        nx.draw_networkx_labels(self.graph, pos, self.node_labels, font_size=11, font_weight='bold', 
                              bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='none'))
        
        title = 'Dromedary Data and Control Flow Graph'
        
        plt.title(title, fontsize=16, fontweight='bold', pad=20)
        plt.axis('off')
        
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgreen', markersize=12, label='User Data'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightblue', markersize=12, label='Function/Tool'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightcyan', markersize=12, label='Tool Result'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightsalmon', markersize=12, label='System Operation'),
        ]
        
        if self.has_cycles:
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=12, label='Cycle Node')
            )
            legend_elements.append(
                plt.Line2D([0], [0], color='red', linewidth=3, label='Cycle Edge')
            )
        
        plt.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        plt.tight_layout()
        plt.show()
        
        return f"Interactive visualization displayed"


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
