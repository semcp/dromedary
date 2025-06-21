#!/usr/bin/env python3

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "src"))

from dromedary.models import CloudDriveFile, SharingPermission

# MCP imports
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions


@dataclass
class FileStoreContext:
    files: List[CloudDriveFile]


# Global file store
file_store: FileStoreContext = FileStoreContext(files=[])


def _populate_test_data():
    """Populate stores with fake data for testing purposes"""
    fake_files = [
        CloudDriveFile(
            id_="file-001",
            filename="project-proposal.docx",
            content="This is a project proposal document with detailed specifications...",
            owner="mossaka@bluesparrowtech.com",
            last_modified=datetime.now() - timedelta(hours=24),
            size=len("This is a project proposal document with detailed specifications...".encode('utf-8'))
        ),
        CloudDriveFile(
            id_="file-002", 
            filename="meeting-notes.txt",
            content="Meeting notes from the last team sync:\n- Discussed project timeline\n- Reviewed budget allocations\n- Planned next deliverables",
            owner="mossaka@bluesparrowtech.com",
            last_modified=datetime.now() - timedelta(hours=8),
            size=len("Meeting notes from the last team sync:\n- Discussed project timeline\n- Reviewed budget allocations\n- Planned next deliverables".encode('utf-8'))
        )
    ]
    
    file_store.files.extend(fake_files)


# Initialize test data
_populate_test_data()

# Create the MCP server
server = Server("file-storage")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available file storage tools."""
    return [
        types.Tool(
            name="append_to_file",
            description="Append content to a file in the cloud drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file to append content to"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to append to the file"
                    }
                },
                "required": ["file_id", "content"]
            }
        ),
        types.Tool(
            name="search_files_by_filename",
            description="Get a file from a cloud drive by its filename. It returns a list of files",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name of the file to retrieve"
                    }
                },
                "required": ["filename"]
            }
        ),
        types.Tool(
            name="create_file",
            description="Create a new file in the cloud drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name of the file to create"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content of the file to create"
                    }
                },
                "required": ["filename", "content"]
            }
        ),
        types.Tool(
            name="delete_file",
            description="Delete a file from a cloud drive by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file to delete"
                    }
                },
                "required": ["file_id"]
            }
        ),
        types.Tool(
            name="get_file_by_id",
            description="Get a file from a cloud drive by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file to retrieve"
                    }
                },
                "required": ["file_id"]
            }
        ),
        types.Tool(
            name="list_files",
            description="Retrieve all files in the cloud drive",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="share_file",
            description="Share a file with a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file to share"
                    },
                    "email": {
                        "type": "string",
                        "description": "The email of the user to share the file with"
                    },
                    "permission": {
                        "type": "string",
                        "description": "The permission level to grant the user (r or rw)"
                    }
                },
                "required": ["file_id", "email", "permission"]
            }
        ),
        types.Tool(
            name="search_files",
            description="Search for files in the cloud drive by content",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The string to search for in the files"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="update_file_content",
            description="Update the content of an existing file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file to update"
                    },
                    "content": {
                        "type": "string",
                        "description": "The new content for the file"
                    }
                },
                "required": ["file_id", "content"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "append_to_file":
        file_id = arguments["file_id"]
        content = arguments["content"]
        
        for file in file_store.files:
            if file.id_ == file_id:
                file.content += content
                file.last_modified = datetime.now()
                file.size = len(file.content.encode('utf-8'))
                return [types.TextContent(
                    type="text",
                    text=json.dumps(file.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"File {file_id} not found"})
        )]
    
    elif name == "search_files_by_filename":
        filename = arguments["filename"]
        results = [file for file in file_store.files if filename.lower() in file.filename.lower()]
        
        return [types.TextContent(
            type="text",
            text=json.dumps([file.dict() for file in results], default=str, indent=2)
        )]
    
    elif name == "create_file":
        filename = arguments["filename"]
        content = arguments["content"]
        
        file = CloudDriveFile(
            id_=str(uuid.uuid4()),
            filename=filename,
            content=content,
            owner="mossaka@bluesparrowtech.com",
            last_modified=datetime.now(),
            size=len(content.encode('utf-8'))
        )
        file_store.files.append(file)
        
        return [types.TextContent(
            type="text",
            text=json.dumps(file.dict(), default=str, indent=2)
        )]
    
    elif name == "delete_file":
        file_id = arguments["file_id"]
        
        for i, file in enumerate(file_store.files):
            if file.id_ == file_id:
                deleted_file = file_store.files.pop(i)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(deleted_file.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"File {file_id} not found"})
        )]
    
    elif name == "get_file_by_id":
        file_id = arguments["file_id"]
        
        for file in file_store.files:
            if file.id_ == file_id:
                return [types.TextContent(
                    type="text",
                    text=json.dumps(file.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"File {file_id} not found"})
        )]
    
    elif name == "list_files":
        return [types.TextContent(
            type="text",
            text=json.dumps([file.dict() for file in file_store.files], default=str, indent=2)
        )]
    
    elif name == "share_file":
        file_id = arguments["file_id"]
        email = arguments["email"]
        permission = arguments["permission"]
        
        for file in file_store.files:
            if file.id_ == file_id:
                file.shared_with[email] = SharingPermission(permission)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(file.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"File {file_id} not found"})
        )]
    
    elif name == "search_files":
        query = arguments["query"]
        results = [file for file in file_store.files if query.lower() in file.content.lower()]
        
        return [types.TextContent(
            type="text",
            text=json.dumps([file.dict() for file in results], default=str, indent=2)
        )]
    
    elif name == "update_file_content":
        file_id = arguments["file_id"]
        content = arguments["content"]
        
        for file in file_store.files:
            if file.id_ == file_id:
                file.content = content
                file.last_modified = datetime.now()
                file.size = len(content.encode('utf-8'))
                return [types.TextContent(
                    type="text",
                    text=json.dumps(file.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"File {file_id} not found"})
        )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="files://all",
            name="All Files",
            description="All files in the system as a formatted list",
            mimeType="text/markdown"
        ),
        types.Resource(
            uri="files://recent",
            name="Recent Files",
            description="Recently modified files as a formatted list",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Handle resource reading."""
    if uri == "files://all":
        files_text = "# All Files\n\n"
        for file in file_store.files:
            files_text += f"## {file.filename}\n"
            files_text += f"ID: {file.id_}\n"
            files_text += f"Owner: {file.owner}\n"
            files_text += f"Size: {file.size} bytes\n"
            files_text += f"Last Modified: {file.last_modified.strftime('%Y-%m-%d %H:%M')}\n"
            if file.shared_with:
                files_text += f"Shared with: {', '.join(f'{email} ({perm.value})' for email, perm in file.shared_with.items())}\n"
            files_text += f"Content Preview: {file.content[:100]}{'...' if len(file.content) > 100 else ''}\n\n---\n\n"
        return files_text
    
    elif uri == "files://recent":
        # Sort by last modified date (most recent first)
        recent_files = sorted(file_store.files, key=lambda f: f.last_modified, reverse=True)[:10]
        
        files_text = "# Recently Modified Files\n\n"
        for file in recent_files:
            files_text += f"## {file.filename}\n"
            files_text += f"Last Modified: {file.last_modified.strftime('%Y-%m-%d %H:%M')}\n"
            files_text += f"Size: {file.size} bytes\n"
            files_text += f"Content Preview: {file.content[:100]}{'...' if len(file.content) > 100 else ''}\n\n"
        return files_text
    
    else:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="file-storage",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main()) 