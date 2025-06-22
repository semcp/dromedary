#!/usr/bin/env python3

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import sys
from pathlib import Path

# Add project root to path for package imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcp_servers.models import Email, EmailStatus, EmailContact

# MCP imports
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions


@dataclass
class EmailStoreContext:
    emails: List[Email]
    contacts: List[EmailContact]


# Global email store
email_store: EmailStoreContext = EmailStoreContext(emails=[], contacts=[])


def _populate_test_data():
    """Populate stores with fake data for testing purposes"""
    contacts = [
        EmailContact(email="mossaka@bluesparrowtech.com", name="Mossaka"),
        EmailContact(email="john.doe@bluesparrowtech.com", name="John Doe"),
        EmailContact(email="jane.smith@bluesparrowtech.com", name="Jane Smith"),
        EmailContact(email="bob.wilson@techcorp.com", name="Bob Wilson"),
        EmailContact(email="alice.cooper@clientcorp.com", name="Alice Cooper"),
        EmailContact(email="mike.johnson@bluesparrowtech.com", name="Mike Johnson"),
    ]
    email_store.contacts.extend(contacts)
    
    fake_emails = [
        Email(
            id_="email-001",
            sender="mike.johnson@bluesparrowtech.com",
            recipients=["mossaka@bluesparrowtech.com"],
            subject="Re: Project Meeting Tomorrow",
            body="Hi Mossaka,\n\nThanks for setting up the meeting for tomorrow. Bob will be there at 2 PM in Conference Room A.\n\nBob's email is bob.wilson@techcorp.com in case you need to reach me.\n\nBest regards,\nBob Wilson",
            status=EmailStatus.received,
            timestamp=datetime.now() - timedelta(hours=2),
            read=False
        ),
        Email(
            id_="email-002", 
            sender="alice.cooper@clientcorp.com",
            recipients=["mossaka@bluesparrowtech.com"],
            subject="Follow up on quarterly report",
            body="Hi Mossaka,\n\nI wanted to follow up on the quarterly report we discussed. When can we schedule a review meeting?\n\nContact me at alice.cooper@clientcorp.com\n\nBest,\nAlice Cooper",
            status=EmailStatus.received,
            timestamp=datetime.now() - timedelta(hours=6),
            read=False
        ),
        Email(
            id_="email-003",
            sender="mike.johnson@bluesparrowtech.com", 
            recipients=["mossaka@bluesparrowtech.com"],
            subject="Team lunch this Friday",
            body="Hey Mossaka,\n\nWe're organizing a team lunch this Friday at 12:30 PM. Let me know if you can make it!\n\nCheers,\nMike",
            status=EmailStatus.received,
            timestamp=datetime.now() - timedelta(hours=12),
            read=True
        )
    ]
    fake_emails.reverse()
    email_store.emails.extend(fake_emails)


# Initialize test data
_populate_test_data()

# Create the MCP server
server = Server("email-system")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available email tools."""
    return [
        types.Tool(
            name="send_email",
            description="Sends an email with the given body to the given addresses",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The list with the email addresses of the recipients"
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email"
                    },
                    "body": {
                        "type": "string",
                        "description": "The body of the email"
                    },
                    "attachments": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "The list of attachments to include in the email. If null, no attachments are included"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The list of email addresses to include in the CC field. If null, no email addresses are included"
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The list of email addresses to include in the BCC field. If null, no email addresses are included"
                    }
                },
                "required": ["recipients", "subject", "body"]
            }
        ),
        types.Tool(
            name="delete_email",
            description="Deletes the email with the given email_id from the inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The id of the email to delete"
                    }
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="get_unread_emails",
            description="Returns all the unread emails in the inbox. Each email has a sender, a subject, and a body. The emails are marked as read after this function is called",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="get_sent_emails",
            description="Returns all the sent emails in the inbox. Each email has a recipient, a subject, and a body",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="get_received_emails",
            description="Returns all the received emails in the inbox. Each email has a sender, a subject, and a body",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="get_draft_emails",
            description="Returns all the draft emails in the inbox. Each email has a recipient, a subject, and a body",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="search_emails",
            description="Searches for emails in the inbox that contain the given query in the subject or body",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search for in the email subject or body. If empty, all emails are returned"
                    },
                    "sender": {
                        "type": "string",
                        "description": "The email address of the sender. If null, all emails are searched"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="search_contacts_by_name",
            description="Finds contacts in the inbox's contact list by name. It returns a list of contacts that match the given name",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The name of the contacts to search for"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="search_contacts_by_email",
            description="Finds contacts in the inbox's contact list by email. It returns a list of contacts that match the given email",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The email of the contacts to search for"
                    }
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "send_email":
        recipients = arguments["recipients"]
        subject = arguments["subject"]
        body = arguments["body"]
        attachments = arguments.get("attachments", [])
        cc = arguments.get("cc", [])
        bcc = arguments.get("bcc", [])
        
        email = Email(
            id_=str(uuid.uuid4()),
            sender="mossaka@bluesparrowtech.com",
            recipients=recipients,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            status=EmailStatus.sent,
            timestamp=datetime.now(),
            attachments=attachments
        )
        email_store.emails.append(email)
        
        result = {
            "id": email.id_,
            "sender": email.sender,
            "recipients": email.recipients,
            "subject": email.subject,
            "body": email.body,
            "status": email.status.value,
            "timestamp": email.timestamp.isoformat()
        }
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, default=str, indent=2)
        )]
    
    elif name == "delete_email":
        email_id = arguments["email_id"]
        
        for i, email in enumerate(email_store.emails):
            if email.id_ == email_id:
                del email_store.emails[i]
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"success": f"Email {email_id} deleted successfully"})
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Email {email_id} not found"})
        )]
    
    elif name == "get_unread_emails":
        unread = [email for email in email_store.emails if not email.read]
        for email in unread:
            email.read = True
        
        results = [
            {
                "id": email.id_,
                "sender": email.sender,
                "recipients": email.recipients,
                "subject": email.subject,
                "body": email.body,
                "status": email.status.value,
                "timestamp": email.timestamp.isoformat()
            }
            for email in unread
        ]
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "get_sent_emails":
        sent_emails = [email for email in email_store.emails if email.status == EmailStatus.sent]
        
        results = [
            {
                "id": email.id_,
                "sender": email.sender,
                "recipients": email.recipients,
                "subject": email.subject,
                "body": email.body,
                "status": email.status.value,
                "timestamp": email.timestamp.isoformat()
            }
            for email in sent_emails
        ]
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "get_received_emails":
        received_emails = [email for email in email_store.emails if email.status == EmailStatus.received]
        
        results = [
            {
                "id": email.id_,
                "sender": email.sender,
                "recipients": email.recipients,
                "subject": email.subject,
                "body": email.body,
                "status": email.status.value,
                "timestamp": email.timestamp.isoformat(),
                "read": email.read
            }
            for email in received_emails
        ]
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "get_draft_emails":
        draft_emails = [email for email in email_store.emails if email.status == EmailStatus.draft]
        
        results = [
            {
                "id": email.id_,
                "sender": email.sender,
                "recipients": email.recipients,
                "subject": email.subject,
                "body": email.body,
                "status": email.status.value,
                "timestamp": email.timestamp.isoformat()
            }
            for email in draft_emails
        ]
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "search_emails":
        query = arguments["query"].lower()
        sender = arguments.get("sender")
        
        results = []
        for email in email_store.emails:
            if query in email.subject.lower() or query in email.body.lower():
                if sender is None or email.sender == sender:
                    results.append({
                        "id": email.id_,
                        "sender": email.sender,
                        "recipients": email.recipients,
                        "subject": email.subject,
                        "body": email.body,
                        "status": email.status.value,
                        "timestamp": email.timestamp.isoformat(),
                        "read": email.read
                    })
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "search_contacts_by_name":
        query = arguments["query"].lower()
        
        results = [
            {"email": contact.email, "name": contact.name}
            for contact in email_store.contacts 
            if query in contact.name.lower()
        ]
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "search_contacts_by_email":
        query = arguments["query"].lower()
        
        results = [
            {"email": contact.email, "name": contact.name}
            for contact in email_store.contacts 
            if query in contact.email.lower()
        ]
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="email-system",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main()) 