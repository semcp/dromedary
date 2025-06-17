#!/usr/bin/env python3

import asyncio
import json
import subprocess
import sys
import tempfile
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TestEmailMCPServer(unittest.TestCase):
    """Test suite for the Email MCP server."""
    
    async def get_email_client(self):
        """Get a client connected to the email server."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path("mcp_servers/email/email_server.py"))],
        )
        return stdio_client(server_params)
    
    def test_email_server_initialization(self):
        """Test that the email server initializes correctly."""
        async def run_test():
            async with await self.get_email_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List available tools
                    tools = await session.list_tools()
                    tool_names = [tool.name for tool in tools.tools]
                    
                    expected_tools = {
                        "send_email", "delete_email", "get_unread_emails",
                        "get_sent_emails", "get_received_emails", "get_draft_emails",
                        "search_emails", "search_contacts_by_name", "search_contacts_by_email"
                    }
                    
                    self.assertTrue(expected_tools.issubset(set(tool_names)))
        
        asyncio.run(run_test())
    
    def test_send_email_tool(self):
        """Test the send_email tool."""
        async def run_test():
            async with await self.get_email_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "send_email",
                        arguments={
                            "recipients": ["test@example.com"],
                            "subject": "Test Email",
                            "body": "This is a test email body."
                        }
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    response_data = json.loads(response_text)
                    
                    self.assertIn("id", response_data)
                    self.assertEqual(response_data["subject"], "Test Email")
                    self.assertEqual(response_data["recipients"], ["test@example.com"])
                    self.assertEqual(response_data["status"], "sent")
        
        asyncio.run(run_test())
    
    def test_get_received_emails_tool(self):
        """Test the get_received_emails tool."""
        async def run_test():
            async with await self.get_email_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("get_received_emails", arguments={})
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    emails = json.loads(response_text)
                    
                    self.assertIsInstance(emails, list)
                    self.assertGreater(len(emails), 0)
                    
                    # Check that each email has the expected fields
                    for email in emails:
                        self.assertIn("id", email)
                        self.assertIn("sender", email)
                        self.assertIn("subject", email)
                        self.assertIn("body", email)
                        self.assertIn("status", email)
                        self.assertEqual(email["status"], "received")
        
        asyncio.run(run_test())
    
    def test_search_emails_tool(self):
        """Test the search_emails tool."""
        async def run_test():
            async with await self.get_email_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "search_emails",
                        arguments={"query": "meeting"}
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    emails = json.loads(response_text)
                    
                    self.assertIsInstance(emails, list)
                    # Verify that all returned emails contain "meeting" in subject or body
                    for email in emails:
                        text_content = (email["subject"] + " " + email["body"]).lower()
                        self.assertIn("meeting", text_content)
        
        asyncio.run(run_test())
    
    def test_search_contacts_tool(self):
        """Test the search_contacts_by_name tool."""
        async def run_test():
            async with await self.get_email_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "search_contacts_by_name",
                        arguments={"query": "Bob"}
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    contacts = json.loads(response_text)
                    
                    self.assertIsInstance(contacts, list)
                    self.assertGreater(len(contacts), 0)
                    
                    # Verify that all returned contacts contain "Bob" in name
                    for contact in contacts:
                        self.assertIn("Bob", contact["name"])
                        self.assertIn("email", contact)
        
        asyncio.run(run_test())


class TestCalendarMCPServer(unittest.TestCase):
    """Test suite for the Calendar MCP server."""
    
    async def get_calendar_client(self):
        """Get a client connected to the calendar server."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path("mcp_servers/calendar/calendar_server.py"))],
        )
        return stdio_client(server_params)
    
    def test_calendar_server_initialization(self):
        """Test that the calendar server initializes correctly."""
        async def run_test():
            async with await self.get_calendar_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List available tools
                    tools = await session.list_tools()
                    tool_names = [tool.name for tool in tools.tools]
                    
                    expected_tools = {
                        "get_current_day", "search_calendar_events", "get_day_calendar_events",
                        "create_calendar_event", "cancel_calendar_event", "reschedule_calendar_event",
                        "add_calendar_event_participants"
                    }
                    
                    self.assertTrue(expected_tools.issubset(set(tool_names)))
        
        asyncio.run(run_test())
    
    def test_get_current_day_tool(self):
        """Test the get_current_day tool."""
        async def run_test():
            async with await self.get_calendar_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("get_current_day", arguments={})
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response - it returns {"current_day": "2025-06-16"}
                    response_text = result.content[0].text
                    response_data = json.loads(response_text)
                    
                    self.assertIn("current_day", response_data)
                    # Verify it's a valid date format
                    datetime.strptime(response_data["current_day"], '%Y-%m-%d')
        
        asyncio.run(run_test())
    
    def test_create_calendar_event_tool(self):
        """Test the create_calendar_event tool."""
        async def run_test():
            async with await self.get_calendar_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    tomorrow = datetime.now() + timedelta(days=1)
                    start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
                    end_time = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    
                    result = await session.call_tool(
                        "create_calendar_event",
                        arguments={
                            "title": "Test Meeting",
                            "start_time": start_time.strftime('%Y-%m-%d %H:%M'),
                            "end_time": end_time.strftime('%Y-%m-%d %H:%M'),
                            "description": "This is a test meeting",
                            "participants": ["test@example.com"],
                            "location": "Conference Room"
                        }
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    event_data = json.loads(response_text)
                    
                    # The model uses id_ field, not id
                    self.assertIn("id_", event_data)
                    self.assertEqual(event_data["title"], "Test Meeting")
                    self.assertEqual(event_data["description"], "This is a test meeting")
                    self.assertEqual(event_data["location"], "Conference Room")
                    self.assertEqual(event_data["participants"], ["test@example.com"])
                    self.assertEqual(event_data["status"], "confirmed")
        
        asyncio.run(run_test())
    
    def test_search_calendar_events_tool(self):
        """Test the search_calendar_events tool."""
        async def run_test():
            async with await self.get_calendar_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "search_calendar_events",
                        arguments={"query": "meeting"}
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    events = json.loads(response_text)
                    
                    self.assertIsInstance(events, list)
                    # Verify that all returned events contain "meeting" in title or description
                    for event in events:
                        text_content = (event["title"] + " " + event["description"]).lower()
                        self.assertIn("meeting", text_content)
        
        asyncio.run(run_test())


class TestFileStoreMCPServer(unittest.TestCase):
    """Test suite for the FileStore MCP server."""
    
    async def get_filestore_client(self):
        """Get a client connected to the filestore server."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path("mcp_servers/filestore/filestore_server.py"))],
        )
        return stdio_client(server_params)
    
    def test_filestore_server_initialization(self):
        """Test that the filestore server initializes correctly."""
        async def run_test():
            async with await self.get_filestore_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List available tools
                    tools = await session.list_tools()
                    tool_names = [tool.name for tool in tools.tools]
                    
                    expected_tools = {
                        "append_to_file", "search_files_by_filename", "create_file",
                        "delete_file", "get_file_by_id", "list_files", "share_file", "search_files"
                    }
                    
                    self.assertTrue(expected_tools.issubset(set(tool_names)))
        
        asyncio.run(run_test())
    
    def test_list_files_tool(self):
        """Test the list_files tool."""
        async def run_test():
            async with await self.get_filestore_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("list_files", arguments={})
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    files = json.loads(response_text)
                    
                    self.assertIsInstance(files, list)
                    self.assertGreater(len(files), 0)
                    
                    # Check that each file has the expected fields - model uses id_ not id
                    for file in files:
                        self.assertIn("id_", file)
                        self.assertIn("filename", file)
                        self.assertIn("content", file)
                        self.assertIn("owner", file)
                        self.assertIn("last_modified", file)
                        self.assertIn("size", file)
        
        asyncio.run(run_test())
    
    def test_create_file_tool(self):
        """Test the create_file tool."""
        async def run_test():
            async with await self.get_filestore_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "create_file",
                        arguments={
                            "filename": "test.txt",
                            "content": "This is test content for the file."
                        }
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    file_data = json.loads(response_text)
                    
                    # The model uses id_ field, not id
                    self.assertIn("id_", file_data)
                    self.assertEqual(file_data["filename"], "test.txt")
                    self.assertEqual(file_data["content"], "This is test content for the file.")
                    self.assertEqual(file_data["owner"], "mossaka@bluesparrowtech.com")
                    self.assertEqual(file_data["size"], len("This is test content for the file."))
        
        asyncio.run(run_test())
    
    def test_search_files_tool(self):
        """Test the search_files tool."""
        async def run_test():
            async with await self.get_filestore_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "search_files",
                        arguments={"query": "project"}
                    )
                    
                    self.assertFalse(result.isError)
                    self.assertGreater(len(result.content), 0)
                    
                    # Parse the response
                    response_text = result.content[0].text
                    files = json.loads(response_text)
                    
                    self.assertIsInstance(files, list)
                    # Verify that all returned files contain "project" in content
                    for file in files:
                        self.assertIn("project", file["content"].lower())
        
        asyncio.run(run_test())
    
    def test_get_file_by_id_tool(self):
        """Test the get_file_by_id tool."""
        async def run_test():
            async with await self.get_filestore_client() as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # First get list of files to find a valid ID
                    list_result = await session.call_tool("list_files", arguments={})
                    files = json.loads(list_result.content[0].text)
                    
                    if files:
                        # Use id_ field instead of id
                        file_id = files[0]["id_"]
                        
                        result = await session.call_tool(
                            "get_file_by_id",
                            arguments={"file_id": file_id}
                        )
                        
                        self.assertFalse(result.isError)
                        self.assertGreater(len(result.content), 0)
                        
                        # Parse the response
                        response_text = result.content[0].text
                        file_data = json.loads(response_text)
                        
                        self.assertEqual(file_data["id_"], file_id)
                        self.assertIn("filename", file_data)
                        self.assertIn("content", file_data)
        
        asyncio.run(run_test())


class TestMCPServerIntegration(unittest.TestCase):
    """Integration tests for all MCP servers."""
    
    def test_all_servers_can_start(self):
        """Test that all servers can start and respond to basic requests."""
        async def run_test():
            servers = [
                ("email", "mcp_servers/email/email_server.py"),
                ("calendar", "mcp_servers/calendar/calendar_server.py"),
                ("filestore", "mcp_servers/filestore/filestore_server.py")
            ]
            
            for server_name, server_path in servers:
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=[str(Path(server_path))],
                )
                
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        # Test that we can list tools
                        tools = await session.list_tools()
                        self.assertGreater(len(tools.tools), 0)
                        
                        print(f"✅ {server_name} server started successfully with {len(tools.tools)} tools")
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main() 