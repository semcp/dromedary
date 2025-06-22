from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple, Optional

class SourceType(Enum):
    USER = "user"
    TOOL = "tool"
    SYSTEM = "system"
    INVOCATION = "invocation"

@dataclass
class Source:
    type: SourceType
    identifier: Optional[str] = None
    inner_source: Optional["Source"] = None

@dataclass
class CapabilityValue:
    """Refactored: Wraps a value with a reference to its node in the provenance graph."""
    node_id: int
    value: Any

    def __hash__(self):
        return self.node_id

    def __eq__(self, other):
        if not isinstance(other, CapabilityValue):
            return False
        return self.node_id == other.node_id

class ProvenanceGraph:
    """The new centralized graph manager."""
    def __init__(self):
        self.nodes: Dict[int, Any] = {}
        self.sources: Dict[int, Source] = {}
        self.edges: List[Tuple[int, int]] = []
        self._node_counter: int = 0

    def add_node(self, value: Any, source: Source, dependency_ids: Optional[List[int]] = None) -> int:
        """Adds a new node and its connecting edges, returning the new node's ID."""
        node_id = self._node_counter
        self._node_counter += 1

        self.nodes[node_id] = value
        self.sources[node_id] = source

        if dependency_ids:
            for dep_id in dependency_ids:
                self.edges.append((dep_id, node_id))
        
        return node_id

    def get_value(self, node_id: int) -> Any:
        return self.nodes.get(node_id)

    def get_ancestors_subgraph(self, leaf_node_ids: List[int]) -> Tuple[Dict[int, Any], List[Tuple[int, int]]]:
        """
        Performs a traversal from leaf nodes to find all ancestor nodes
        and their immediate children to form a complete subgraph.
        """
        # Step 1: Backward pass to find all ancestors
        ancestor_nodes = set(leaf_node_ids)
        queue = list(leaf_node_ids)
        
        parent_map: Dict[int, List[int]] = {node_id: [] for node_id in self.nodes}
        for from_id, to_id in self.edges:
            parent_map[to_id].append(from_id)

        head = 0
        while head < len(queue):
            current_id = queue[head]
            head += 1
            
            for parent_id in parent_map.get(current_id, []):
                if parent_id not in ancestor_nodes:
                    ancestor_nodes.add(parent_id)
                    queue.append(parent_id)
        
        # Step 2: One-step forward pass to include immediate children
        nodes_to_include = set(ancestor_nodes)
        for node_id in ancestor_nodes:
            # Find all edges starting from the current node
            for from_id, to_id in self.edges:
                if from_id == node_id:
                    nodes_to_include.add(to_id)

        # Step 3: Filter nodes and edges for the final subgraph
        subgraph_nodes = {node_id: self.nodes[node_id] for node_id in nodes_to_include if node_id in self.nodes}
        subgraph_edges = [(from_id, to_id) for from_id, to_id in self.edges 
                          if from_id in nodes_to_include and to_id in nodes_to_include]
                          
        return subgraph_nodes, subgraph_edges

class ProvenanceTracker:
    """Interacts with the central graph to track provenances."""
    def __init__(self, graph: ProvenanceGraph):
        self.graph = graph

    def literal(self, value: Any) -> CapabilityValue:
        source = Source(type=SourceType.USER, identifier="literal")
        node_id = self.graph.add_node(value, source)
        return CapabilityValue(node_id=node_id, value=value)

    def from_tool(self, value: Any, tool_name: str, dependencies: Optional[List[CapabilityValue]] = None) -> CapabilityValue:
        """Creates a CapabilityValue from a tool's output with its dependencies."""
        source = Source(type=SourceType.TOOL, identifier=tool_name)
        
        dependency_ids = [dep.node_id for dep in dependencies] if dependencies else []
        
        node_id = self.graph.add_node(value, source, dependency_ids=dependency_ids)
        
        return CapabilityValue(node_id=node_id, value=value)

    def from_system(self, value: Any, identifier: str = "dromedary") -> CapabilityValue:
        source = Source(type=SourceType.SYSTEM, identifier=identifier)
        node_id = self.graph.add_node(value, source)
        return CapabilityValue(node_id=node_id, value=value)

    def from_computation(self, value: Any, dependencies: List[CapabilityValue]) -> CapabilityValue:
        dependency_ids = [dep.node_id for dep in dependencies]
        source = Source(type=SourceType.SYSTEM, identifier="dromedary")
        node_id = self.graph.add_node(value, source, dependency_ids)
        return CapabilityValue(node_id=node_id, value=value)
    
    def unwrap(self, obj: Any) -> Any:
        """Central place to unwrap values."""
        if isinstance(obj, CapabilityValue):
            return obj.value
        return obj 