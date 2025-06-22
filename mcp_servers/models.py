from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Union
from pydantic import BaseModel, Field, EmailStr


class EmailStatus(Enum):
    sent = 'sent'
    received = 'received'
    draft = 'draft'


class EventStatus(Enum):
    confirmed = 'confirmed'
    canceled = 'canceled'


class SharingPermission(Enum):
    r = 'r'
    rw = 'rw'


class CalendarEvent(BaseModel):
    id_: str = Field(description='The unique identifier of the event')
    title: str = Field(description='The title of the event')
    description: str = Field(description='The description of the event')
    start_time: datetime = Field(description='The start time of the event')
    end_time: datetime = Field(description='The end time of the event')
    location: Optional[str] = Field(description='The location of the event')
    participants: List[EmailStr] = Field(description='The list of the emails of the participants')
    all_day: bool = Field(default=False, description='Whether the event is all day')
    status: EventStatus = Field(default=EventStatus.confirmed, description='The status of the event')
    
    def __str__(self):
        time_str = f"{self.start_time.strftime('%Y-%m-%d %H:%M')}"
        if not self.all_day:
            time_str += f" - {self.end_time.strftime('%H:%M')}"
        location_str = f" at {self.location}" if self.location else ""
        participants_str = f" ({len(self.participants)} participants)" if self.participants else ""
        return f"{self.title}{location_str} on {time_str}{participants_str}"


class Email(BaseModel):
    id_: str = Field(description='The unique identifier of the email')
    sender: EmailStr = Field(description='The email of the sender')
    recipients: List[EmailStr] = Field(description='The list of the emails of the recipients')
    cc: List[EmailStr] = Field(default_factory=list, description='The list of the emails of the CC recipients')
    bcc: List[EmailStr] = Field(default_factory=list, description='The list of the emails of the BCC recipients')
    subject: str = Field(description='The subject of the email')
    body: str = Field(description='The body of the email')
    status: EmailStatus = Field(default=EmailStatus.sent, description='The status of the email')
    read: bool = Field(default=False, description='Whether the email has been read')
    timestamp: datetime = Field(default_factory=datetime.now, description='The timestamp of the email')
    attachments: List[Union[str, CalendarEvent]] = Field(default_factory=list)
    
    def __str__(self):
        to_str = ", ".join(self.recipients[:2])
        if len(self.recipients) > 2:
            to_str += f" +{len(self.recipients) - 2} more"
        return f"{self.subject} | To: {to_str} | {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class EmailContact(BaseModel):
    email: EmailStr = Field()
    name: str = Field()
    
    def __str__(self):
        return f"👤 {self.name} <{self.email}>"


class CloudDriveFile(BaseModel):
    id_: str = Field(description='The unique identifier of the file')
    filename: str = Field(description='The name of the file')
    content: str = Field(description='The content of the file')
    owner: EmailStr = Field(description='The email of the owner of the file')
    last_modified: datetime = Field(description='The last modified timestamp')
    shared_with: Dict[EmailStr, SharingPermission] = Field(default_factory=dict, description='The object containing emails with their sharing permissions')
    size: int = Field(default=0, description='The size of the file in bytes')
    
    def __str__(self):
        size_str = f"{self.size:,} bytes" if self.size < 1024 else f"{self.size/1024:.1f} KB"
        shared_str = f" (shared with {len(self.shared_with)})" if self.shared_with else ""
        return f"{self.filename} | {size_str} | Modified: {self.last_modified.strftime('%Y-%m-%d %H:%M')}{shared_str}"

