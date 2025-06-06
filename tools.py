import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, TypeVar, Type
from langchain.tools import BaseTool
from pydantic import BaseModel
from models import (
    Email, EmailStatus, EmailContact, CalendarEvent, EventStatus,
    CloudDriveFile, SharingPermission
)

_T = TypeVar('_T', bound=BaseModel)

class EmailStore:
    def __init__(self):
        self.emails: List[Email] = []
        self.contacts: List[EmailContact] = [
            EmailContact(email="mossaka@bluesparrowtech.com", name="Mossaka"),
            EmailContact(email="john.doe@bluesparrowtech.com", name="John Doe"),
            EmailContact(email="jane.smith@bluesparrowtech.com", name="Jane Smith"),
            EmailContact(email="bob.wilson@techcorp.com", name="Bob Wilson"),
            EmailContact(email="alice.cooper@clientcorp.com", name="Alice Cooper"),
        ]

class CalendarStore:
    def __init__(self):
        self.events: List[CalendarEvent] = []

class FileStore:
    def __init__(self):
        self.files: List[CloudDriveFile] = []

email_store = EmailStore()
calendar_store = CalendarStore()
file_store = FileStore()

def _populate_test_data():
    """Populate stores with fake data for testing purposes"""
    from datetime import datetime, timedelta
    
    # Add fake received emails
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
    # Reverse the order of the emails
    fake_emails.reverse()
    
    # Add fake calendar events
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
    
    # Add fake files
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
    
    # Populate the stores
    email_store.emails.extend(fake_emails)
    calendar_store.events.extend(fake_events)
    file_store.files.extend(fake_files)
    
    # Add more contacts
    additional_contacts = [
        EmailContact(email="bob.wilson@techcorp.com", name="Bob Wilson"),
        EmailContact(email="alice.cooper@clientcorp.com", name="Alice Cooper"),
        EmailContact(email="mike.johnson@bluesparrowtech.com", name="Mike Johnson"),
    ]
    email_store.contacts.extend(additional_contacts)

# For testing purpose
def reset_all_stores():
    """Reset all stores to their initial state and repopulate with fresh test data"""
    global email_store, calendar_store, file_store
    
    email_store = EmailStore()
    calendar_store = CalendarStore()
    file_store = FileStore()
    
    _populate_test_data()

# Populate test data on module import
_populate_test_data()

class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = """Sends an email with the given `body` to the given `address`. Returns a dictionary with the email details.
:param recipients: The list with the email addresses of the recipients.
:param subject: The subject of the email.
:param body: The body of the email.
:param attachments: The list of attachments to include in the email. If `null`, no attachments are included.
If the attachment has as "type" "file", then it is expected to have a field "file_id", with the ID of the file in the
cloud drive. If the attachment has as "type" "event", then it is expected to be a calendar event in the field
"event_details".
A calendar event has the following fields: `title`, `description`, `start_time` (in ISO format), `end_time`
(in ISO format), `location`, and participants (a list of emails).
:param cc: The list of email addresses to include in the CC field. If `null`, no email addresses are included.
:param bcc: The list of email addresses to include in the BCC field. If `null`, no email addresses are included."""
    
    def _run(self, recipients: List[str], subject: str, body: str, 
             attachments: Optional[List[Dict]] = None, 
             cc: Optional[List[str]] = None, 
             bcc: Optional[List[str]] = None) -> Email:
        email = Email(
            id_=str(uuid.uuid4()),
            sender="mossaka@bluesparrowtech.com",
            recipients=recipients,
            cc=cc or [],
            bcc=bcc or [],
            subject=subject,
            body=body,
            status=EmailStatus.sent,
            timestamp=datetime.now(),
            attachments=attachments or []
        )
        email_store.emails.append(email)
        return email


class DeleteEmailTool(BaseTool):
    name: str = "delete_email"
    description: str = """Deletes the email with the given `email_id` from the inbox.
:param email_id: The id of the email to delete."""
    
    def _run(self, email_id: str) -> str:
        for i, email in enumerate(email_store.emails):
            if email.id_ == email_id:
                del email_store.emails[i]
                return f"Email {email_id} deleted successfully"
        return f"Email {email_id} not found"


class GetUnreadEmailsTool(BaseTool):
    name: str = "get_unread_emails"
    description: str = """Returns all the unread emails in the inbox. Each email has a sender, a subject, and a body.
The emails are marked as read after this function is called."""
    
    def _run(self) -> List[Email]:
        unread = [email for email in email_store.emails if not email.read]
        for email in unread:
            email.read = True
        return unread


class GetSentEmailsTool(BaseTool):
    name: str = "get_sent_emails"
    description: str = "Returns all the sent emails in the inbox. Each email has a recipient, a subject, and a body."
    
    def _run(self) -> List[Email]:
        return [email for email in email_store.emails if email.status == EmailStatus.sent]


class GetReceivedEmailsTool(BaseTool):
    name: str = "get_received_emails"
    description: str = "Returns all the received emails in the inbox. Each email has a sender, a subject, and a body."
    
    def _run(self) -> List[Email]:
        return [email for email in email_store.emails if email.status == EmailStatus.received]


class GetDraftEmailsTool(BaseTool):
    name: str = "get_draft_emails"
    description: str = "Returns all the draft emails in the inbox. Each email has a recipient, a subject, and a body."
    
    def _run(self) -> List[Email]:
        return [email for email in email_store.emails if email.status == EmailStatus.draft]


class SearchEmailsTool(BaseTool):
    name: str = "search_emails"
    description: str = """Searches for emails in the inbox that contain the given query in the subject or body. If `address` is provided,
only emails from that address are searched.
:param query: The query to search for in the email subject or body. If empty, all emails are returned.
:param sender: The email address of the sender. If `null`, all emails are searched. Use `search_contacts_by_name`
if the email address is unknown."""
    
    def _run(self, query: str, sender: Optional[str] = None) -> List[Email]:
        results = []
        for email in email_store.emails:
            if query.lower() in email.subject.lower() or query.lower() in email.body.lower():
                if sender is None or email.sender == sender:
                    results.append(email)
        return results


class SearchContactsByNameTool(BaseTool):
    name: str = "search_contacts_by_name"
    description: str = """Finds contacts in the inbox's contact list by name.
It returns a list of contacts that match the given name.
:param query: The name of the contacts to search for."""
    
    def _run(self, query: str) -> List[EmailContact]:
        return [contact for contact in email_store.contacts 
                if query.lower() in contact.name.lower()]


class SearchContactsByEmailTool(BaseTool):
    name: str = "search_contacts_by_email"
    description: str = """Finds contacts in the inbox's contact list by email.
It returns a list of contacts that match the given email.
:param query: The email of the contacts to search for."""
    
    def _run(self, query: str) -> List[EmailContact]:
        return [contact for contact in email_store.contacts 
                if query.lower() in contact.email.lower()]


class GetCurrentDayTool(BaseTool):
    name: str = "get_current_day"
    description: str = """Returns the current day in ISO format, e.g. '2022-01-01'.
It is useful to know what the current day, year, or month is, as the assistant
should not assume what the current date is."""
    
    def _run(self) -> str:
        return datetime.now().strftime('%Y-%m-%d')


class SearchCalendarEventsTool(BaseTool):
    name: str = "search_calendar_events"
    description: str = """Searches calendar events that match the given query in the tile or the description. If provided, filters events by date.
:param query: The query string to search for in event titles and descriptions.
:param date: The date for which to search events. Must be in format YYYY-MM-DD. If `null`, searches all events."""
    
    def _run(self, query: str, date: Optional[str] = None) -> List[CalendarEvent]:
        results = []
        for event in calendar_store.events:
            if query.lower() in event.title.lower() or query.lower() in event.description.lower():
                if date is None or event.start_time.strftime('%Y-%m-%d') == date:
                    results.append(event)
        return results


class GetDayCalendarEventsTool(BaseTool):
    name: str = "get_day_calendar_events"
    description: str = """Returns the appointments for the given `day`. Returns a list of dictionaries with informations about each meeting.
:param day: The day for which to return the appointments. Must be in format YYYY-MM-DD."""
    
    def _run(self, day: str) -> List[CalendarEvent]:
        return [event for event in calendar_store.events 
                if event.start_time.strftime('%Y-%m-%d') == day]


class CreateCalendarEventTool(BaseTool):
    name: str = "create_calendar_event"
    description: str = """Creates a new calendar event with the given details and adds it to the calendar.
It also sends an email to the participants with the event details.
:param title: The title of the event.
:param start_time: The start time of the event. Must be in format YYYY-MM-DD HH:MM.
:param end_time: The end time of the event. Must be in format YYYY-MM-DD HH:MM.
:param description: The description of the event.
:param participants: The list of participants' email addresses. If `null`, no participants are set. The calendar owner's
email address is always included..
:param location: The location of the event. If `null`, no location is set."""
    
    def _run(self, title: str, start_time: str, end_time: str, description: str,
             participants: Optional[List[str]] = None, location: Optional[str] = None) -> CalendarEvent:
        event = CalendarEvent(
            id_=str(uuid.uuid4()),
            title=title,
            description=description,
            start_time=datetime.strptime(start_time, '%Y-%m-%d %H:%M'),
            end_time=datetime.strptime(end_time, '%Y-%m-%d %H:%M'),
            location=location,
            participants=participants or [],
            status=EventStatus.confirmed
        )
        calendar_store.events.append(event)
        return event


class CancelCalendarEventTool(BaseTool):
    name: str = "cancel_calendar_event"
    description: str = """Cancels the event with the given `event_id`. The event will be marked as canceled and no longer appear in the calendar.
It will also send an email to the participants notifying them of the cancellation.
:param event_id: The ID of the event to cancel."""
    
    def _run(self, event_id: str) -> str:
        for event in calendar_store.events:
            if event.id_ == event_id:
                event.status = EventStatus.canceled
                return f"Event {event_id} canceled successfully"
        return f"Event {event_id} not found"


class RescheduleCalendarEventTool(BaseTool):
    name: str = "reschedule_calendar_event"
    description: str = """Reschedules the event with the given `event_id` to the new start and end times.
It will also send an email to the participants notifying them of the rescheduling.
:param event_id: The ID of the event to reschedule.
:param new_start_time: The new start time of the event. Must be in format YYYY-MM-DD HH:MM.
:param new_end_time: The new end time of the event. Must be in format YYYY-MM-DD HH:MM.
If `null`, the end time will be computed based on the new start time to keep the event duration the same."""
    
    def _run(self, event_id: str, new_start_time: str, new_end_time: Optional[str] = None) -> CalendarEvent:
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
                return event
        raise ValueError(f"Event {event_id} not found")


class AddCalendarEventParticipantsTool(BaseTool):
    name: str = "add_calendar_event_participants"
    description: str = """Adds the given `participants` to the event with the given `event_id`.
It will also email the new participants notifying them of the event.
:param event_id: The ID of the event to add participants to.
:param participants: The list of participants' email addresses to add to the event."""
    
    def _run(self, event_id: str, participants: List[str]) -> CalendarEvent:
        for event in calendar_store.events:
            if event.id_ == event_id:
                event.participants.extend(participants)
                return event
        raise ValueError(f"Event {event_id} not found")


class AppendToFileTool(BaseTool):
    name: str = "append_to_file"
    description: str = """Append content to a file in the cloud drive.
:param file_id: The ID of the file to append content to.
:param content: The content to append to the file."""
    
    def _run(self, file_id: str, content: str) -> CloudDriveFile:
        for file in file_store.files:
            if file.id_ == file_id:
                file.content += content
                file.last_modified = datetime.now()
                file.size = len(file.content.encode('utf-8'))
                return file
        raise ValueError(f"File {file_id} not found")


class SearchFilesByFilenameTool(BaseTool):
    name: str = "search_files_by_filename"
    description: str = """Get a file from a cloud drive by its filename. It returns a list of files.
Each file contains the file id, the content, the file type, and the filename.
:param filename: The name of the file to retrieve."""
    
    def _run(self, filename: str) -> List[CloudDriveFile]:
        return [file for file in file_store.files if filename.lower() in file.filename.lower()]


class CreateFileTool(BaseTool):
    name: str = "create_file"
    description: str = """Create a new file in the cloud drive.
:param filename: The name of the file to create.
:param content: The content of the file to create."""
    
    def _run(self, filename: str, content: str) -> CloudDriveFile:
        file = CloudDriveFile(
            id_=str(uuid.uuid4()),
            filename=filename,
            content=content,
            owner="mossaka@bluesparrowtech.com",
            last_modified=datetime.now(),
            size=len(content.encode('utf-8'))
        )
        file_store.files.append(file)
        return file


class DeleteFileTool(BaseTool):
    name: str = "delete_file"
    description: str = """Delete a file from a cloud drive by its filename.
It returns the file that was deleted.
:param file_id: The name of the file to delete."""
    
    def _run(self, file_id: str) -> CloudDriveFile:
        for i, file in enumerate(file_store.files):
            if file.id_ == file_id:
                return file_store.files.pop(i)
        raise ValueError(f"File {file_id} not found")


class GetFileByIdTool(BaseTool):
    name: str = "get_file_by_id"
    description: str = """Get a file from a cloud drive by its ID.
:param file_id: The ID of the file to retrieve."""
    
    def _run(self, file_id: str) -> CloudDriveFile:
        for file in file_store.files:
            if file.id_ == file_id:
                return file
        raise ValueError(f"File {file_id} not found")


class ListFilesTool(BaseTool):
    name: str = "list_files"
    description: str = "Retrieve all files in the cloud drive."
    
    def _run(self) -> List[CloudDriveFile]:
        return file_store.files


class ShareFileTool(BaseTool):
    name: str = "share_file"
    description: str = """Share a file with a user.
:param file_id: The ID of the file to share.
:param email: The email of the user to share the file with.
:param permission: The permission level to grant the user."""
    
    def _run(self, file_id: str, email: str, permission: str) -> CloudDriveFile:
        for file in file_store.files:
            if file.id_ == file_id:
                file.shared_with[email] = SharingPermission(permission)
                return file
        raise ValueError(f"File {file_id} not found")


class SearchFilesTool(BaseTool):
    name: str = "search_files"
    description: str = """Search for files in the cloud drive by content.

:param query: The string to search for in the files."""
    
    def _run(self, query: str) -> List[CloudDriveFile]:
        return [file for file in file_store.files if query.lower() in file.content.lower()]


class QueryAIAssistantTool(BaseTool):
    name: str = "query_ai_assistant"
    description: str = """Queries a Large Language Model with `query` and returns the language model's output. It must be used to process
unstructured data into structured one.
It is absolutely imperative that you use this function to parse data whose structure you don't know insted of parsing using
regular expressions and/or
string manipulation.
There is no need to specify the expected output format in the query itself as the format will be specified on the side with
`output_schema`
with the build-in API of the assistant.
:param query: a string with the query. Make sure to provide sufficient instructions to the AI assistant so that it can
understand what it needs to do.
Avoid just passing it tool outputs without additional instructions.
:param output_schema: a Pydantic BaseModel class that specifies the expected output format from the model.
The fields should have types as specific as possible to make sure the parsing is correct and accurate.
allowed types are:
- `int`
- `str`
- `float`
- `bool`
- `datetime.datetime` (assume `datetime` is imported from `datetime`)
- `enum.Enum` classes
- `pydantic.BaseModel` classes that you can define (assume that `BaseModel` is imported from `pydantic`) or are already
defined in these instructions.
- `pydantic.EmailStr` (assume that `EmailStr` is imported from `pydantic`)"""
    
    def _run(self, query: str, output_schema: Type[_T]) -> _T:
        if "current year" in query.lower():
            return output_schema(result=str(datetime.now().year))
        elif "parse email" in query.lower():
            return output_schema(sender="example@email.com", subject="Example", body="Example body")
        else:
            return output_schema(result="AI assistant response")


def get_all_tools():
    return [
        SendEmailTool(),
        DeleteEmailTool(),
        GetUnreadEmailsTool(),
        GetSentEmailsTool(),
        GetReceivedEmailsTool(),
        GetDraftEmailsTool(),
        SearchEmailsTool(),
        SearchContactsByNameTool(),
        SearchContactsByEmailTool(),
        GetCurrentDayTool(),
        SearchCalendarEventsTool(),
        GetDayCalendarEventsTool(),
        CreateCalendarEventTool(),
        CancelCalendarEventTool(),
        RescheduleCalendarEventTool(),
        AddCalendarEventParticipantsTool(),
        AppendToFileTool(),
        SearchFilesByFilenameTool(),
        CreateFileTool(),
        DeleteFileTool(),
        GetFileByIdTool(),
        ListFilesTool(),
        ShareFileTool(),
        SearchFilesTool(),
        QueryAIAssistantTool(),
    ] 