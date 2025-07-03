import asyncio
import json
from .mcp.client import MCPClientManager

async def main():
    async with MCPClientManager() as manager:
        print(f"Available servers: {manager.get_all_servers()}")

        result = await manager._connections["github"].call_tool("list_issues", {"owner": "bytecodealliance", "repo": "wasmtime", "perPage": 3})

        parsed_content = json.loads(result.content[0].text)
        print(json.dumps(parsed_content[0], indent=2))

        labels_per_item = result.meta.get('labels', [])
        if not labels_per_item:
            print("No labels found in the result.")
            return
        
        print(json.dumps(labels_per_item[0], indent=2))


if __name__ == "__main__":
    asyncio.run(main())