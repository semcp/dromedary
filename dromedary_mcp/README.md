# Dromedary MCP

A Python library for connecting to MCP servers, discovering available tools, and exposing them as Python callable functions.

## Limitations 🚧

- It currently only supports stdio MCP servers. Future work will include support for HTTP MCP servers and Authentication.
- It currently only supports MCP Tools.

## Quick Start

### Basic Usage 📝

```python
from dromedary_mcp import create_mcp_tool_loader

# Create and initialize tool loader
tool_loader = create_mcp_tool_loader("path/to/mcp-config.json")

# Get available tools
tools = tool_loader.get_available_tools()
print(f"Available tools: {tools}")

# Execute a tool
email_tool = tool_loader.get_tool_function("send_email")
result = email_tool(to="user@example.com", subject="Hello", body="Test message")
```

### Alternative Usage with Context Manager

```python
from dromedary_mcp import MCPManager, MCPToolMapper, MCPToolLoader

# For fine-grained control over lifecycle
with MCPManager("path/to/mcp-config.json") as manager:
    tool_mapper = MCPToolMapper(manager)
    tool_loader = MCPToolLoader(tool_mapper, manager)
    
    # Use tools
    if tool_loader.has_tool("create_file"):
        create_file = tool_loader.get_tool_function("create_file")
        result = create_file(name="test.txt", content="Hello world")
```

### Integration with Apps

```python
from dromedary_mcp import create_mcp_tool_loader

class MyApplication:
    def __init__(self, mcp_config_path):
        self.mcp_tools = create_mcp_tool_loader(mcp_config_path)
    
    def execute_workflow(self):
        # Check available tools
        tools = self.mcp_tools.get_available_tools()
        
        # Execute tools as needed
        if "send_email" in tools:
            email_func = self.mcp_tools.get_tool_function("send_email")
            email_func(to="admin@company.com", subject="Workflow Complete")
```

## Configuration

MCP servers are configured via JSON:

```json
{
  "mcpServers": {
    "email-server": {
      "type": "stdio",
      "command": "python",
      "args": ["email_server.py"],
      "env": {}
    },
    "file-server": {
      "type": "stdio", 
      "command": "python",
      "args": ["file_server.py"],
      "env": {}
    }
  }
}
```

## API Reference

### `create_mcp_tool_loader(config_path)`

Factory function that creates a fully initialized tool loader.

### MCPToolLoader

Provides a unified, high-level interface for accessing MCP tools.

- `get_available_tools()` - List available tool names
- `get_tool_function(name)` - Get callable function for a tool
- `has_tool(name)` - Check if tool exists
- `get_tool_info(name)` - Get detailed tool information
- `get_connected_servers()` - List connected server names

### MCPManager

Context manager for MCP server connections.

- `initialize()` - Start background connections
- `shutdown()` - Clean shutdown of connections
- `call_tool_sync(name, args)` - Execute tool synchronously

### MCPToolMapper

Maps MCP tools to Python callables.

- `get_function(name)` - Get mapped function
- `get_all_functions()` - Get all mapped functions
- `refresh_mappings()` - Refresh after reconnection
