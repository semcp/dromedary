from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Policy(ABC):
    """Abstract base class for all policy implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def evaluate(self, tool_args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Evaluate the policy and return a list of violations."""
        pass


class EmailPolicy(Policy):
    """Policy for email-related operations."""
    
    def evaluate(self, tool_args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[str]:
        violations = []
        
        recipients = tool_args.get("recipients", [])
        allowed_recipients = set(self.config.get("allowed_recipients", []))
        restricted_recipients = set(self.config.get("restricted_recipients", []))
        
        for recipient in recipients:
            if recipient in restricted_recipients:
                violations.append(f"Email sending to {recipient} is not allowed")
            elif recipient not in allowed_recipients:
                violations.append(f"Email sending to {recipient} is not in the allowed recipients list")
        
        violations.extend(self._check_recipient_provenance(context))
        
        return violations
    
    def _check_recipient_provenance(self, context: Optional[Dict[str, Any]]) -> List[str]:
        """Check the data provenance of email recipients"""
        violations = []
        
        if not context:
            return violations
        
        capability_values = context.get("capability_values", {})
        provenance_graph = context.get("provenance_graph")
        
        # Try to find recipients capability value - check both parameter name and positional args
        recipients_cap = capability_values.get("recipients")
        
        if not recipients_cap or not hasattr(recipients_cap, 'node_id') or not provenance_graph:
            return violations
        
        untrusted_tools = set(self.config.get("untrusted_provenance_sources", []))
        
        # Get the source for this node from the provenance graph
        source = provenance_graph.sources.get(recipients_cap.node_id)
        if source and source.type.value == "tool":
            if source.identifier in untrusted_tools:
                violations.append(f"Cannot send email to address from untrusted source '{source.identifier}'. Use the search_contacts_by_name or search_contacts_by_email tools to get the email address.")
        
        return violations


class CalendarPolicy(Policy):
    """Policy for calendar-related operations."""
    
    def evaluate(self, tool_args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[str]:
        violations = []
        
        # Check start time for event creation
        start_time_str = tool_args.get("start_time")
        if start_time_str:
            violations.extend(self._validate_working_hours(start_time_str))
        
        # Check new start time for rescheduling
        new_start_time_str = tool_args.get("new_start_time")
        if new_start_time_str:
            violations.extend(self._validate_working_hours(new_start_time_str, is_reschedule=True))
        
        # Check participants
        participants = tool_args.get("participants", [])
        max_participants = self.config.get("max_participants", 10)
        if len(participants) > max_participants:
            violations.append(f"Cannot create calendar events with more than {max_participants} participants")
        
        business_emails = set(self.config.get("business_emails", []))
        for participant in participants:
            if participant not in business_emails:
                violations.append(f"Participant {participant} is not a recognized business email")
        
        return violations
    
    def _validate_working_hours(self, time_str: str, is_reschedule: bool = False) -> List[str]:
        """Validate that the time falls within working hours."""
        violations = []
        
        try:
            start_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            start_hour = start_time.hour
            
            allowed_start = self.config.get("allowed_working_hours_start", 8)
            allowed_end = self.config.get("allowed_working_hours_end", 18)
            
            action = "reschedule" if is_reschedule else "create"
            
            if start_hour < allowed_start:
                violations.append(f"Cannot {action} calendar events before {allowed_start} AM")
            elif start_hour >= allowed_end:
                violations.append(f"Cannot {action} calendar events after {allowed_end - 12} PM")
        except ValueError:
            time_field = "new_start_time" if is_reschedule else "start_time"
            violations.append(f"Invalid {time_field} format")
        
        return violations


class FilePolicy(Policy):
    """Policy for file-related operations."""
    
    def evaluate(self, tool_args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[str]:
        violations = []
        
        sensitive_patterns = self.config.get("sensitive_file_patterns", [])
        allowed_permissions = set(self.config.get("allowed_share_permissions", []))
        business_emails = set(self.config.get("business_emails", []))
        
        # Check file content for sensitive information
        file_content = context.get("file_content", "") if context else ""
        
        if self._contains_sensitive_content(file_content, sensitive_patterns):
            violations.append("Cannot perform operation on files containing sensitive information")
        
        # File-specific validations
        filename = tool_args.get("filename")
        if filename and self._contains_sensitive_filename(filename, sensitive_patterns):
            violations.append(f"Cannot create files with sensitive names: {filename}")
        
        # Share-specific validations
        email = tool_args.get("email")
        if email and email not in business_emails:
            violations.append(f"Cannot share files with external email: {email}")
        
        permission = tool_args.get("permission")
        if permission and permission not in allowed_permissions:
            violations.append(f"Invalid sharing permission: {permission}")
        
        return violations
    
    def _contains_sensitive_content(self, content: str, patterns: List[str]) -> bool:
        """Check if content contains sensitive patterns."""
        if not content:
            return False
        lower_content = content.lower()
        return any(pattern in lower_content for pattern in patterns)
    
    def _contains_sensitive_filename(self, filename: str, patterns: List[str]) -> bool:
        """Check if filename contains sensitive patterns."""
        if not filename:
            return False
        lower_filename = filename.lower()
        return any(pattern in lower_filename for pattern in patterns) 