#!/usr/bin/env python3

import asyncio
import json
import subprocess
import sys
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TestEmailMCPServer:
    
    async def get_email_client(self):
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path("mcp_servers/email/email_server.py"))],
        )
        return stdio_client(server_params)
    
    @pytest.mark.asyncio
    async def test_email_server_initialization(self):
        async with await self.get_email_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                
                expected_tools = {
                    "send_email", "delete_email", "get_unread_emails",
                    "get_sent_emails", "get_received_emails", "get_draft_emails",
                    "search_emails", "search_contacts_by_name", "search_contacts_by_email"
                }
                
                assert expected_tools.issubset(set(tool_names))
    
    @pytest.mark.asyncio
    async def test_send_email_tool(self):
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
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                response_data = json.loads(response_text)
                
                assert "id" in response_data
                assert response_data["subject"] == "Test Email"
                assert response_data["recipients"] == ["test@example.com"]
                assert response_data["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_get_received_emails_tool(self):
        async with await self.get_email_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool("get_received_emails", arguments={})
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                emails = json.loads(response_text)
                
                assert isinstance(emails, list)
                assert len(emails) > 0
                
                for email in emails:
                    assert "id" in email
                    assert "sender" in email
                    assert "subject" in email
                    assert "body" in email
                    assert "status" in email
                    assert email["status"] == "received"
    
    @pytest.mark.asyncio
    async def test_search_emails_tool(self):
        async with await self.get_email_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "search_emails",
                    arguments={"query": "meeting"}
                )
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                emails = json.loads(response_text)
                
                assert isinstance(emails, list)
                for email in emails:
                    text_content = (email["subject"] + " " + email["body"]).lower()
                    assert "meeting" in text_content
    
    @pytest.mark.asyncio
    async def test_search_contacts_tool(self):
        async with await self.get_email_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "search_contacts_by_name",
                    arguments={"query": "Bob"}
                )
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                contacts = json.loads(response_text)
                
                assert isinstance(contacts, list)
                assert len(contacts) > 0
                
                for contact in contacts:
                    assert "Bob" in contact["name"]
                    assert "email" in contact


class TestCalendarMCPServer:
    
    async def get_calendar_client(self):
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path("mcp_servers/calendar/calendar_server.py"))],
        )
        return stdio_client(server_params)
    
    @pytest.mark.asyncio
    async def test_calendar_server_initialization(self):
        async with await self.get_calendar_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                
                expected_tools = {
                    "get_current_day", "search_calendar_events", "get_day_calendar_events",
                    "create_calendar_event", "cancel_calendar_event", "reschedule_calendar_event",
                    "add_calendar_event_participants"
                }
                
                assert expected_tools.issubset(set(tool_names))
    
    @pytest.mark.asyncio
    async def test_get_current_day_tool(self):
        async with await self.get_calendar_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool("get_current_day", arguments={})
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                datetime.strptime(response_text, '%Y-%m-%d')
    
    @pytest.mark.asyncio
    async def test_create_calendar_event_tool(self):
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
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                event_data = json.loads(response_text)
                
                assert "id_" in event_data
                assert event_data["title"] == "Test Meeting"
                assert event_data["description"] == "This is a test meeting"
                assert event_data["location"] == "Conference Room"
                assert event_data["participants"] == ["test@example.com"]
                assert event_data["status"] == "confirmed"
    
    @pytest.mark.asyncio
    async def test_search_calendar_events_tool(self):
        async with await self.get_calendar_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "search_calendar_events",
                    arguments={"query": "meeting"}
                )
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                events = json.loads(response_text)
                
                assert isinstance(events, list)
                for event in events:
                    text_content = (event["title"] + " " + event["description"]).lower()
                    assert "meeting" in text_content


class TestFileStoreMCPServer:
    
    async def get_filestore_client(self):
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path("mcp_servers/filestore/filestore_server.py"))],
        )
        return stdio_client(server_params)
    
    @pytest.mark.asyncio
    async def test_filestore_server_initialization(self):
        async with await self.get_filestore_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                
                expected_tools = {
                    "append_to_file", "search_files_by_filename", "create_file",
                    "delete_file", "get_file_by_id", "list_files", "share_file", "search_files"
                }
                
                assert expected_tools.issubset(set(tool_names))
    
    @pytest.mark.asyncio
    async def test_list_files_tool(self):
        async with await self.get_filestore_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool("list_files", arguments={})
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                files = json.loads(response_text)
                
                assert isinstance(files, list)
                assert len(files) > 0
                
                for file in files:
                    assert "id_" in file
                    assert "filename" in file
                    assert "content" in file
                    assert "owner" in file
                    assert "last_modified" in file
                    assert "size" in file
    
    @pytest.mark.asyncio
    async def test_create_file_tool(self):
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
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                file_data = json.loads(response_text)
                
                assert "id_" in file_data
                assert file_data["filename"] == "test.txt"
                assert file_data["content"] == "This is test content for the file."
                assert file_data["owner"] == "mossaka@bluesparrowtech.com"
                assert file_data["size"] == len("This is test content for the file.")
    
    @pytest.mark.asyncio
    async def test_search_files_tool(self):
        async with await self.get_filestore_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "search_files",
                    arguments={"query": "project"}
                )
                
                assert not result.isError
                assert len(result.content) > 0
                
                response_text = result.content[0].text
                files = json.loads(response_text)
                
                assert isinstance(files, list)
                for file in files:
                    assert "project" in file["content"].lower()
    
    @pytest.mark.asyncio
    async def test_get_file_by_id_tool(self):
        async with await self.get_filestore_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                list_result = await session.call_tool("list_files", arguments={})
                files = json.loads(list_result.content[0].text)
                
                if files:
                    file_id = files[0]["id_"]
                    
                    result = await session.call_tool(
                        "get_file_by_id",
                        arguments={"file_id": file_id}
                    )
                    
                    assert not result.isError
                    assert len(result.content) > 0
                    
                    response_text = result.content[0].text
                    file_data = json.loads(response_text)
                    
                    assert file_data["id_"] == file_id
                    assert "filename" in file_data
                    assert "content" in file_data


class TestMCPServerIntegration:
    
    @pytest.mark.asyncio
    async def test_all_servers_can_start(self):
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
            
            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        tools = await session.list_tools()
                        assert len(tools.tools) > 0
                        
            except Exception as e:
                pytest.fail(f"Server {server_name} failed to start: {e}") 