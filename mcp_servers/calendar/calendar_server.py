#!/usr/bin/env python3

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import List
from dataclasses import dataclass
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import CalendarEvent, EventStatus

# MCP imports
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions


@dataclass
class CalendarStoreContext:
    events: List[CalendarEvent]


# Global calendar store
calendar_store: CalendarStoreContext = CalendarStoreContext(events=[])


def _populate_test_data():
    """Populate stores with fake data for testing purposes"""
    tomorrow = datetime.now() + timedelta(days=1)
    next_week = datetime.now() + timedelta(days=7)
    
    fake_events = [
        CalendarEvent(
            id_="event-001",
            title="Project Review Meeting",
            description="Monthly project review with stakeholders to discuss progress and next steps.",
            start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=15, minute=30, second=0, microsecond=0),
            location="Conference Room A",
            participants=["bob.wilson@techcorp.com", "jane.smith@bluesparrowtech.com"],
            status=EventStatus.confirmed
        ),
        CalendarEvent(
            id_="event-002",
            title="Client Presentation",
            description="Quarterly business review presentation to key clients.",
            start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=11, minute=30, second=0, microsecond=0),
            location="Main Conference Room",
            participants=["alice.cooper@clientcorp.com", "john.doe@bluesparrowtech.com"],
            status=EventStatus.confirmed
        ),
        CalendarEvent(
            id_="event-003",
            title="Team Standup Meeting", 
            description="Daily team standup to sync on progress and blockers.",
            start_time=next_week.replace(hour=9, minute=30, second=0, microsecond=0),
            end_time=next_week.replace(hour=10, minute=0, second=0, microsecond=0),
            location="Team Room B",
            participants=["mike.johnson@bluesparrowtech.com", "jane.smith@bluesparrowtech.com"],
            status=EventStatus.confirmed
        )
    ]
    
    calendar_store.events.extend(fake_events)


# Initialize test data
_populate_test_data()

# Create the MCP server
server = Server("calendar-system")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available calendar tools."""
    return [
        types.Tool(
            name="search_calendar_events",
            description="Search calendar events that match the given query in the title or description",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query string to search for in event titles and descriptions"
                    },
                    "date": {
                        "type": "string",
                        "description": "The date for which to search events. Must be in format YYYY-MM-DD. If null, searches all events"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_day_calendar_events",
            description="Returns the appointments for the given day",
            inputSchema={
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "The day for which to return the appointments. Must be in format YYYY-MM-DD"
                    }
                },
                "required": ["day"]
            }
        ),
        types.Tool(
            name="create_calendar_event",
            description="Creates a new calendar event with the given details and adds it to the calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the event"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "The start time of the event. Must be in format YYYY-MM-DD HH:MM"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The end time of the event. Must be in format YYYY-MM-DD HH:MM"
                    },
                    "description": {
                        "type": "string",
                        "description": "The description of the event"
                    },
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The list of participants' email addresses. If null, no participants are set"
                    },
                    "location": {
                        "type": "string",
                        "description": "The location of the event. If null, no location is set"
                    }
                },
                "required": ["title", "start_time", "end_time", "description"]
            }
        ),
        types.Tool(
            name="cancel_calendar_event",
            description="Cancels the event with the given event_id. The event will be marked as canceled",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to cancel"
                    }
                },
                "required": ["event_id"]
            }
        ),
        types.Tool(
            name="reschedule_calendar_event",
            description="Reschedules the event with the given event_id to the new start and end times",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to reschedule"
                    },
                    "new_start_time": {
                        "type": "string",
                        "description": "The new start time of the event. Must be in format YYYY-MM-DD HH:MM"
                    },
                    "new_end_time": {
                        "type": "string",
                        "description": "The new end time of the event. Must be in format YYYY-MM-DD HH:MM. If null, the end time will be computed based on the new start time to keep the event duration the same"
                    }
                },
                "required": ["event_id", "new_start_time"]
            }
        ),
        types.Tool(
            name="add_calendar_event_participants",
            description="Adds the given participants to the event with the given event_id",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to add participants to"
                    },
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The list of participants' email addresses to add to the event"
                    }
                },
                "required": ["event_id", "participants"]
            }
        ),
        types.Tool(
            name="get_current_day",
            description="Returns the current day in ISO format, e.g. '2022-01-01'. It is useful to know what the current day, year, or month is",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "search_calendar_events":
        query = arguments["query"].lower()
        date = arguments.get("date")
        results = []
        for event in calendar_store.events:
            if query in event.title.lower() or query in event.description.lower():
                if date is None or event.start_time.strftime('%Y-%m-%d') == date:
                    results.append(event.dict())
        
        return [types.TextContent(
            type="text",
            text=json.dumps(results, default=str, indent=2)
        )]
    
    elif name == "get_day_calendar_events":
        day = arguments["day"]
        events = [event for event in calendar_store.events 
                  if event.start_time.strftime('%Y-%m-%d') == day]
        
        return [types.TextContent(
            type="text",
            text=json.dumps([event.dict() for event in events], default=str, indent=2)
        )]
    
    elif name == "create_calendar_event":
        title = arguments["title"]
        start_time = arguments["start_time"]
        end_time = arguments["end_time"]
        description = arguments["description"]
        participants = arguments.get("participants", [])
        location = arguments.get("location")
        
        event = CalendarEvent(
            id_=str(uuid.uuid4()),
            title=title,
            description=description,
            start_time=datetime.strptime(start_time, '%Y-%m-%d %H:%M'),
            end_time=datetime.strptime(end_time, '%Y-%m-%d %H:%M'),
            location=location,
            participants=participants,
            status=EventStatus.confirmed
        )
        calendar_store.events.append(event)
        
        event_dict = event.dict()
        event_dict["status"] = event.status.value  # Convert enum to string
        return [types.TextContent(
            type="text",
            text=json.dumps(event_dict, default=str, indent=2)
        )]
    
    elif name == "cancel_calendar_event":
        event_id = arguments["event_id"]
        for event in calendar_store.events:
            if event.id_ == event_id:
                event.status = EventStatus.canceled
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"success": f"Event {event_id} canceled successfully"})
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Event {event_id} not found"})
        )]
    
    elif name == "reschedule_calendar_event":
        event_id = arguments["event_id"]
        new_start_time = arguments["new_start_time"]
        new_end_time = arguments.get("new_end_time")
        
        for event in calendar_store.events:
            if event.id_ == event_id:
                new_start = datetime.strptime(new_start_time, '%Y-%m-%d %H:%M')
                if new_end_time:
                    new_end = datetime.strptime(new_end_time, '%Y-%m-%d %H:%M')
                else:
                    duration = event.end_time - event.start_time
                    new_end = new_start + duration
                
                event.start_time = new_start
                event.end_time = new_end
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(event.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Event {event_id} not found"})
        )]
    
    elif name == "add_calendar_event_participants":
        event_id = arguments["event_id"]
        participants = arguments["participants"]
        
        for event in calendar_store.events:
            if event.id_ == event_id:
                event.participants.extend(participants)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(event.dict(), default=str, indent=2)
                )]
        
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Event {event_id} not found"})
        )]
    
    elif name == "get_current_day":
        return [types.TextContent(
            type="text",
            text=json.dumps({"current_day": datetime.now().strftime('%Y-%m-%d')})
        )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="calendar://events/all",
            name="All Calendar Events",
            description="All calendar events as a formatted list",
            mimeType="text/markdown"
        ),
        types.Resource(
            uri="calendar://events/today",
            name="Today's Events",
            description="Today's calendar events as a formatted list",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Handle resource reading."""
    if uri == "calendar://events/all":
        events_text = "# All Calendar Events\n\n"
        for event in calendar_store.events:
            events_text += f"## {event.title} ({event.status.value})\n"
            events_text += f"Start: {event.start_time.strftime('%Y-%m-%d %H:%M')}\n"
            events_text += f"End: {event.end_time.strftime('%Y-%m-%d %H:%M')}\n"
            if event.location:
                events_text += f"Location: {event.location}\n"
            if event.participants:
                events_text += f"Participants: {', '.join(event.participants)}\n"
            events_text += f"Description: {event.description}\n\n---\n\n"
        return events_text
    
    elif uri == "calendar://events/today":
        today = datetime.now().strftime('%Y-%m-%d')
        today_events = [event for event in calendar_store.events 
                       if event.start_time.strftime('%Y-%m-%d') == today]
        
        events_text = f"# Today's Events ({today})\n\n"
        if not today_events:
            events_text += "No events scheduled for today.\n"
        else:
            for event in today_events:
                events_text += f"## {event.title}\n"
                events_text += f"Time: {event.start_time.strftime('%H:%M')} - {event.end_time.strftime('%H:%M')}\n"
                if event.location:
                    events_text += f"Location: {event.location}\n"
                events_text += f"Description: {event.description}\n\n"
        return events_text
    
    else:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="calendar-system",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main()) 