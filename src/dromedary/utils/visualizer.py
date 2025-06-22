import matplotlib

# use interactive backend
matplotlib.use('MacOSX')

import matplotlib.pyplot as plt
import networkx as nx
from typing import Dict, Any, List, Tuple
from ..provenance_graph import ProvenanceGraph, SourceType


class GraphBuilder:
    """Responsible for building networkx graphs from ProvenanceGraph data."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_labels = {}
        self.node_colors = {}
        self.topological_order = []
        self.has_cycles = False
        self.cycle_info = []
        
    def clear_graph(self):
        """Clear all graph data."""
        self.graph.clear()
        self.node_labels.clear()
        self.node_colors.clear()
        self.topological_order.clear()
        self.has_cycles = False
        self.cycle_info.clear()
    
    def build_from_subgraph(self, 
                            subgraph_nodes: Dict[int, Any], 
                            subgraph_edges: List[Tuple[int, int]], 
                            prov_graph: ProvenanceGraph,
                            node_id_to_name: Dict[int, str]) -> nx.DiGraph:
        """
        Builds a networkx graph from a pre-filtered subgraph.
        Returns the constructed graph.
        """
        self.clear_graph()
        
        for node_id, value in subgraph_nodes.items():
            self.graph.add_node(node_id)
            label = node_id_to_name.get(node_id, self._format_node_label(value))
            self.node_labels[node_id] = label
            
            source = prov_graph.sources.get(node_id)
            self.node_colors[node_id] = self._get_node_color(source)

        for from_id, to_id in subgraph_edges:
            self.graph.add_edge(from_id, to_id)
            
        self._analyze_graph()
        return self.graph

    def _get_node_color(self, source) -> str:
        """Determines node color based on its Source."""
        if not source:
            return 'lightgray'
        
        if source.type == SourceType.USER:
            return 'lightgreen'
        elif source.type == SourceType.TOOL:
            return 'lightcyan'
        elif source.type == SourceType.INVOCATION:
            return 'mediumpurple'
        elif source.type == SourceType.SYSTEM:
            return 'lightsalmon'
        
        return 'lightgray'

    def _format_node_label(self, value: Any, max_len: int = 25) -> str:
        """Creates a concise, readable label for a node's value."""
        if isinstance(value, str):
            if len(value) > max_len:
                return f'"{value[:max_len]}..."'
            return f'"{value}"'
        
        if isinstance(value, (list, tuple, set)):
            return f"{type(value).__name__} (len={len(value)})"
        
        if isinstance(value, dict):
             return f"dict (len={len(value)})"
        
        if isinstance(value, (int, float, bool)) or value is None:
            return repr(value)

        if hasattr(value, '__name__'):
            return value.__name__
        
        return f"<{type(value).__name__}>"

    def _analyze_graph(self):
        """Analyze the graph for cycles and create topological ordering."""
        self._topological_sort()

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
        """Create a partial topological ordering using strongly connected components."""
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


class GraphRenderer:
    """Responsible for rendering networkx graphs using matplotlib."""
    
    def __init__(self):
        pass
    
    def render_interactive_graph(self, 
                                graph: nx.DiGraph,
                                node_labels: Dict[int, str],
                                node_colors: Dict[int, str],
                                topological_order: List[int],
                                has_cycles: bool = False,
                                cycle_info: List[List[int]] = None) -> str:
        """Render the graph interactively using matplotlib."""
        if len(graph.nodes) == 0:
            return "No dependency graph to visualize"
        
        cycle_info = cycle_info or []
        
        plt.figure(figsize=(16, 10))
        plt.clf()
        
        pos = self._create_layout(graph, topological_order, has_cycles)
        
        rendered_node_colors = self._prepare_node_colors(graph, node_colors, has_cycles, cycle_info)
        
        self._draw_nodes(graph, pos, rendered_node_colors)
        
        edge_colors, edge_widths = self._prepare_edge_styling(graph, has_cycles, cycle_info)
        self._draw_edges(graph, pos, edge_colors, edge_widths)
        
        self._draw_labels(graph, pos, node_labels)
        
        self._setup_plot_styling(has_cycles)
        
        plt.tight_layout()
        plt.show()
        
        return "Interactive visualization displayed"
    
    def _create_layout(self, graph: nx.DiGraph, topological_order: List[int], has_cycles: bool) -> Dict:
        """Create an appropriate layout for the graph."""
        if len(graph.nodes) <= 15:
            return self._create_hierarchical_layout(graph, topological_order)
        else:
            if not has_cycles and topological_order:
                return self._create_topological_layout(graph, topological_order)
            else:
                return nx.spring_layout(graph, k=3.0, iterations=150, seed=42)

    def _create_topological_layout(self, graph: nx.DiGraph, topological_order: List[int]) -> Dict:
        """Create a layout based on topological ordering with proper dependency levels."""
        if not topological_order:
            return nx.spring_layout(graph, k=3.0, iterations=150, seed=42)
        
        pos = {}
        levels = {}
        
        for node in topological_order:
            if graph.in_degree(node) == 0:
                levels[node] = 0
            else:
                max_predecessor_level = -1
                for predecessor in graph.predecessors(node):
                    if predecessor in levels:
                        max_predecessor_level = max(max_predecessor_level, levels[predecessor])
                levels[node] = max_predecessor_level + 1
        
        level_groups = {}
        for node, level in levels.items():
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(node)
        
        x_spacing = 4.0
        y_spacing = 4.0
        
        for level, nodes in level_groups.items():
            x = level * x_spacing
            y_start = -(len(nodes) - 1) * y_spacing / 2
            
            for i, node in enumerate(nodes):
                y = y_start + i * y_spacing
                pos[node] = (x, y)
        
        return pos

    def _create_hierarchical_layout(self, graph: nx.DiGraph, topological_order: List[int]) -> Dict:
        """Create a left-to-right hierarchical layout."""
        if topological_order:
            return self._create_topological_layout(graph, topological_order)
        
        pos = {}
        
        sources = [n for n in graph.nodes() if graph.in_degree(n) == 0]
        
        if not sources:
            return nx.spring_layout(graph, k=3.0, iterations=150, seed=42)
        
        levels = {}
        for node in graph.nodes():
            min_level = float('inf')
            for source in sources:
                try:
                    path_length = nx.shortest_path_length(graph, source, node)
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
        y_spacing = 4.0
        
        for level, nodes in level_groups.items():
            x = level * x_spacing
            y_start = -(len(nodes) - 1) * y_spacing / 2
            
            for i, node in enumerate(nodes):
                y = y_start + i * y_spacing
                pos[node] = (x, y)
        
        return pos
    
    def _prepare_node_colors(self, graph: nx.DiGraph, node_colors: Dict[int, str], 
                           has_cycles: bool, cycle_info: List[List[int]]) -> List[str]:
        """Prepare node colors, highlighting cycle nodes if present."""
        if not has_cycles:
            return [node_colors.get(node, 'lightgray') for node in graph.nodes()]
        
        cycle_nodes = set()
        for cycle in cycle_info:
            cycle_nodes.update(cycle)
        
        highlighted_colors = []
        for node in graph.nodes():
            if node in cycle_nodes:
                highlighted_colors.append('red')
            else:
                highlighted_colors.append(node_colors.get(node, 'lightgray'))
        
        return highlighted_colors
    
    def _draw_nodes(self, graph: nx.DiGraph, pos: Dict, node_colors: List[str]):
        """Draw the nodes of the graph."""
        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=3000, 
                              alpha=0.9, edgecolors='black', linewidths=1)
    
    def _prepare_edge_styling(self, graph: nx.DiGraph, has_cycles: bool, 
                            cycle_info: List[List[int]]) -> Tuple[List[str], List[int]]:
        """Prepare edge colors and widths, highlighting cycle edges if present."""
        edge_colors = []
        edge_widths = []
        
        for edge in graph.edges():
            if has_cycles:
                is_cycle_edge = False
                for cycle in cycle_info:
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
        
        return edge_colors, edge_widths
    
    def _draw_edges(self, graph: nx.DiGraph, pos: Dict, edge_colors: List[str], edge_widths: List[int]):
        """Draw the edges of the graph."""
        nx.draw_networkx_edges(graph, pos, arrows=True, arrowsize=25, alpha=0.8, 
                             edge_color=edge_colors, width=edge_widths, arrowstyle='-|>', 
                             connectionstyle='arc3,rad=0.3', min_source_margin=30, min_target_margin=30)
    
    def _draw_labels(self, graph: nx.DiGraph, pos: Dict, node_labels: Dict[int, str]):
        """Draw the node labels."""
        nx.draw_networkx_labels(graph, pos, node_labels, font_size=11, font_weight='bold', 
                              bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='none'))
    
    def _setup_plot_styling(self, has_cycles: bool):
        """Set up the plot title, legend, and styling."""
        title = 'Dromedary Data and Control Flow Graph'
        plt.title(title, fontsize=16, fontweight='bold', pad=20)
        plt.axis('off')
        
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgreen', markersize=12, label='User Data'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightblue', markersize=12, label='Function/Tool'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightcyan', markersize=12, label='Tool Result'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='mediumpurple', markersize=12, label='Function Call'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightsalmon', markersize=12, label='System Operation'),
        ]
        
        if has_cycles:
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=12, label='Cycle Node')
            )
            legend_elements.append(
                plt.Line2D([0], [0], color='red', linewidth=3, label='Cycle Edge')
            )
        
        plt.legend(handles=legend_elements, loc='upper right', fontsize=10)


class DependencyGraphVisualizer:
    """Coordinates between GraphBuilder and GraphRenderer to visualize dependency graphs."""
    
    def __init__(self):
        self.graph_builder = GraphBuilder()
        self.graph_renderer = GraphRenderer()
        
    def clear_graph(self):
        """Clear the graph data."""
        self.graph_builder.clear_graph()
    
    def build_from_subgraph(self, 
                            subgraph_nodes: Dict[int, Any], 
                            subgraph_edges: List[Tuple[int, int]], 
                            prov_graph: ProvenanceGraph,
                            node_id_to_name: Dict[int, str]):
        """Build a networkx graph from a pre-filtered subgraph."""
        self.graph_builder.build_from_subgraph(subgraph_nodes, subgraph_edges, prov_graph, node_id_to_name)

    def show_interactive_visualization(self) -> str:
        """Show the interactive dependency graph."""
        return self.graph_renderer.render_interactive_graph(
            self.graph_builder.graph,
            self.graph_builder.node_labels,
            self.graph_builder.node_colors,
            self.graph_builder.topological_order,
            self.graph_builder.has_cycles,
            self.graph_builder.cycle_info
        )


class InterpreterVisualized:
    def __init__(self, interpreter_class, **interpreter_kwargs):
        self.interpreter = interpreter_class(**interpreter_kwargs)
        self.visualizer = DependencyGraphVisualizer()
        
        self.initial_globals = set(self.interpreter.globals.keys())
    
    def clear_for_new_conv(self):
        """Clear the dependency graph for a new conversation"""
        self.visualizer.clear_graph()
        if hasattr(self.interpreter, 'reset_globals'):
            self.interpreter.reset_globals()
            self.initial_globals = set(self.interpreter.globals.keys())
        plt.close('all')
    
    def execute(self, code: str) -> Dict[str, Any]:
        """
        Execute is now simpler: it just runs the code. 
        Graph building is deferred until visualization is requested.
        """
        return self.interpreter.execute(code)
    
    def visualize(self) -> str:
        """
        Builds and displays a focused subgraph of the last execution.
        """
        self.visualizer.clear_graph()
        
        prov_graph = self.interpreter.provenance_graph
        if not prov_graph.nodes:
            return "No dependency graph to visualize"

        leaf_node_ids = []
        node_id_to_name: Dict[int, str] = {}
        for name, cap_value in self.interpreter.globals.items():
            if name not in self.initial_globals and hasattr(cap_value, 'node_id'):
                if cap_value.node_id not in leaf_node_ids:
                    leaf_node_ids.append(cap_value.node_id)
            
            if hasattr(cap_value, 'node_id'):
                if cap_value.node_id in node_id_to_name:
                    if name not in node_id_to_name[cap_value.node_id]:
                        node_id_to_name[cap_value.node_id] += f" / {name}"
                else:
                    node_id_to_name[cap_value.node_id] = name
        
        if self.interpreter.last_result:
            last_node_id = self.interpreter.last_result.node_id
            if last_node_id not in leaf_node_ids:
                leaf_node_ids.append(last_node_id)

        if not leaf_node_ids:
            return "No new variables or final result were produced by the script to visualize."

        subgraph_nodes, subgraph_edges = prov_graph.get_ancestors_subgraph(leaf_node_ids)
        
        self.visualizer.build_from_subgraph(
            subgraph_nodes, 
            subgraph_edges, 
            prov_graph,
            node_id_to_name
        )
        
        return self.visualizer.show_interactive_visualization()
