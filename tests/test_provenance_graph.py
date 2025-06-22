from src.dromedary.provenance_graph import ProvenanceGraph, Source, SourceType, ProvenanceTracker, CapabilityValue

def test_add_literal_node():
    graph = ProvenanceGraph()
    source = Source(type=SourceType.USER, identifier="literal")
    node_id = graph.add_node(10, source)
    
    assert node_id == 0
    assert graph.nodes[0] == 10
    assert graph.sources[0] == source
    assert len(graph.edges) == 0

def test_add_computation_node():
    graph = ProvenanceGraph()
    source1 = Source(type=SourceType.USER, identifier="literal")
    dep1_id = graph.add_node(5, source1)

    source2 = Source(type=SourceType.USER, identifier="literal")
    dep2_id = graph.add_node(7, source2)

    comp_source = Source(type=SourceType.SYSTEM, identifier="dromedary")
    result_id = graph.add_node(12, comp_source, dependency_ids=[dep1_id, dep2_id])

    assert result_id == 2
    assert graph.nodes[2] == 12
    assert len(graph.edges) == 2
    assert (0, 2) in graph.edges
    assert (1, 2) in graph.edges

def test_tracker_literal():
    graph = ProvenanceGraph()
    tracker = ProvenanceTracker(graph)
    
    cap_val = tracker.literal("hello")
    assert isinstance(cap_val, CapabilityValue)
    assert cap_val.node_id == 0
    assert cap_val.value == "hello"
    assert graph.nodes[0] == "hello"

def test_tracker_computation():
    graph = ProvenanceGraph()
    tracker = ProvenanceTracker(graph)

    dep1 = tracker.literal(10)
    dep2 = tracker.literal(20)
    
    result_val = tracker.from_computation(30, dependencies=[dep1, dep2])
    
    assert result_val.node_id == 2
    assert result_val.value == 30
    assert graph.nodes[2] == 30
    assert (dep1.node_id, result_val.node_id) in graph.edges
    assert (dep2.node_id, result_val.node_id) in graph.edges

def test_tracker_from_tool():
    graph = ProvenanceGraph()
    tracker = ProvenanceTracker(graph)
    
    cap_val = tracker.from_tool("tool_result", "email_sender")
    assert isinstance(cap_val, CapabilityValue)
    assert cap_val.node_id == 0
    assert cap_val.value == "tool_result"
    assert graph.nodes[0] == "tool_result"
    assert graph.sources[0].type == SourceType.TOOL
    assert graph.sources[0].identifier == "email_sender"

def test_tracker_unwrap():
    graph = ProvenanceGraph()
    tracker = ProvenanceTracker(graph)
    
    cap_val = tracker.literal("wrapped_value")
    unwrapped = tracker.unwrap(cap_val)
    assert unwrapped == "wrapped_value"
    
    plain_value = "plain_value"
    unwrapped_plain = tracker.unwrap(plain_value)
    assert unwrapped_plain == "plain_value"

def test_tracker_from_system():
    graph = ProvenanceGraph()
    tracker = ProvenanceTracker(graph)
    
    cap_val = tracker.from_system("system_value", "builtin")
    assert isinstance(cap_val, CapabilityValue)
    assert cap_val.node_id == 0
    assert cap_val.value == "system_value"
    assert graph.nodes[0] == "system_value"
    assert graph.sources[0].type == SourceType.SYSTEM
    assert graph.sources[0].identifier == "builtin"

def test_tracker_from_tool_with_dependencies():
    graph = ProvenanceGraph()
    tracker = ProvenanceTracker(graph)
    
    dep1 = tracker.literal("recipient@example.com")
    dep2 = tracker.literal("Hello World")
    dep3 = tracker.from_system(lambda: "send_email", "mcp")
    
    result_val = tracker.from_tool("email_sent", "send_email", dependencies=[dep3, dep1, dep2])
    
    assert result_val.node_id == 3
    assert result_val.value == "email_sent"
    assert graph.nodes[3] == "email_sent"
    assert graph.sources[3].type == SourceType.TOOL
    assert graph.sources[3].identifier == "send_email"
    
    assert (dep3.node_id, result_val.node_id) in graph.edges
    assert (dep1.node_id, result_val.node_id) in graph.edges
    assert (dep2.node_id, result_val.node_id) in graph.edges

def test_tool_dependency_chain_integration():
    """Test that tool calls create proper flow-through dependency chains: args -> invocation -> result."""
    from src.dromedary.interpreter import PythonInterpreter
    
    interpreter = PythonInterpreter(enable_policies=False)
    
    # Create a mock tool that accepts dependencies and returns a CapabilityValue
    def mock_send_email(recipients, subject, body, dependencies=None):
        result_str = f"Email sent to {recipients} with subject: {subject}"
        dependencies = dependencies or []
        return interpreter.provenance.from_tool(result_str, "send_email", dependencies=dependencies)
    
    mock_send_email._needs_capability_values = True
    interpreter.globals['send_email'] = interpreter.provenance.from_system(mock_send_email, "mock_tool")
    
    # Execute code that uses the tool
    code = """
recipient = "test@example.com"
subject = "Test Subject"
body = "Test Body"
result = send_email(recipient, subject, body)
"""
    
    execution_result = interpreter.execute(code)
    assert execution_result["success"] is True
    
    graph = interpreter.provenance_graph
    result_node_id = execution_result["result"].node_id
    
    # Get all ancestors of the result node
    ancestors, _ = graph.get_ancestors_subgraph([result_node_id])
    
    # Verify that the tool function node exists in ancestors
    tool_function_nodes = [node_id for node_id, source in graph.sources.items()
                          if source.type.value == "system" and source.identifier == "mock_tool"]
    assert len(tool_function_nodes) > 0
    tool_function_node = tool_function_nodes[0]
    assert tool_function_node in ancestors
    
    # Verify that the string literals exist in ancestors
    string_literals = [node_id for node_id, value in ancestors.items() 
                      if isinstance(value, str) and value in ["test@example.com", "Test Subject", "Test Body"]]
    assert len(string_literals) >= 3  # All three string arguments should be present
    
    # NEW MODEL: Find the invocation node (should be the direct parent of the result)
    result_parent_ids = [from_id for from_id, to_id in graph.edges if to_id == result_node_id]
    assert len(result_parent_ids) == 1, "Result should have exactly one parent (the invocation node)"
    
    invocation_node_id = result_parent_ids[0]
    invocation_source = graph.sources[invocation_node_id]
    assert invocation_source.type.value == "invocation", "Result's parent should be an invocation node"
    
    # Verify that the invocation node has the tool function and arguments as its parents
    invocation_parent_ids = [from_id for from_id, to_id in graph.edges if to_id == invocation_node_id]
    
    # The invocation should depend on the tool function and all arguments
    assert tool_function_node in invocation_parent_ids, "Invocation should depend on the tool function"
    for literal_id in string_literals:
        assert literal_id in invocation_parent_ids, f"Invocation should depend on argument {graph.nodes[literal_id]}"
    
    # Verify the result contains the expected content
    assert "Email sent to" in execution_result["result"].value
    assert "test@example.com" in execution_result["result"].value
    assert "Test Subject" in execution_result["result"].value 