#!/usr/bin/env python3
"""
Run the P-LLM interpreter standalone for testing and debugging.
"""

import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import patch, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from interpreter import PythonInterpreter
from dromedary_mcp.tool_loader import MCPToolLoader

async def run_interpreter():
    """Run interpreter with MCP tools."""
    print("=" * 60)
    print("Running P-LLM Interpreter")
    print("=" * 60)
    
    config_path = "mcp_servers/mcp-servers-config.json"
    
    if not Path(config_path).exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    # Initialize MCP tool loader
    print("Initializing MCP connections...")
    tool_loader = MCPToolLoader(config_path)
    success = await tool_loader.initialize()
    
    if not success:
        print("❌ Failed to initialize MCP connections")
        return
        
    print("✅ MCP initialization successful")
    
    available_tools = tool_loader.get_available_tools()
    connected_servers = tool_loader.get_connected_servers()
    
    print(f"Available tools: {available_tools}")
    print(f"Connected servers: {connected_servers}")
    
    # Create interpreter with AI assistant mocked
    with patch('interpreter.init_chat_model') as mock_init_chat:
        mock_init_chat.return_value = Mock()
        
        interpreter = PythonInterpreter(enable_policies=False, mcp_tool_loader=tool_loader)
        
        print("Type 'quit' to exit")
        print("=" * 60)
        
        try:
            while True:
                try:
                    code = input(">>> ").strip()
                    
                    if code.lower() in ['quit', 'exit', 'q']:
                        break
                        
                    if not code:
                        continue
                        
                    print("Executing...")
                    result = interpreter.execute(code)
                    
                    if result['success']:
                        if result['result'] is not None:
                            print(f"Result: {result['result']}")
                    else:
                        print(f"Error ({result.get('error_type', 'unknown')}): {result['error']}")
                        
                except KeyboardInterrupt:
                    print("\nGoodbye!")
                    break
                except EOFError:
                    # Handle EOF (e.g., when input is piped)
                    print("\nEOF reached. Exiting...")
                    break
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    
        finally:
            print("Shutting down MCP connections...")
            await tool_loader.shutdown()
            print("Done.")

def main():
    """Main function to run the interpreter."""
    asyncio.run(run_interpreter())

if __name__ == "__main__":
    main() 