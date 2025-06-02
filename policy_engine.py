import os
import json
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class PolicyViolationError(Exception):
    def __init__(self, message: str, violations: List[str]):
        super().__init__(message)
        self.violations = violations

class PolicyEngine:
    def __init__(self, policies_dir: str = "policies"):
        self.policies_dir = Path(policies_dir)
        self.policy_rules = {}
        self._load_policies()
    
    # TODO: this is now hardcoded, but in the future, I'd like to use industry standard
    # policy languages such as Rego to define policies.
    def _load_policies(self):
        """Load policy rules from configuration files"""
        
        self.policy_rules = {
            "email_policy": {
                "allowed_recipients": {
                    "bob.wilson@techcorp.com",
                    "alice.cooper@clientcorp.com",
                    "emma.johnson@bluesparrowtech.com",
                    "john.doe@bluesparrowtech.com",
                    "jane.smith@bluesparrowtech.com",
                },
                "restricted_recipients": {
                    "mike.johnson@bluesparrowtech.com",
                }
            },
            "calendar_policy": {
                "allowed_working_hours_start": 8,
                "allowed_working_hours_end": 18,
                "max_participants": 10,
                "business_emails": {
                    "emma.johnson@bluesparrowtech.com",
                    "john.doe@bluesparrowtech.com", 
                    "jane.smith@bluesparrowtech.com",
                    "mike.johnson@bluesparrowtech.com",
                    "bob.wilson@techcorp.com",
                    "alice.cooper@clientcorp.com",
                }
            },
            "file_policy": {
                "sensitive_file_patterns": [
                    "confidential",
                    "secret",
                    "private",
                    "password",
                    "key"
                ],
                "allowed_share_permissions": {
                    "read",
                    "write"
                },
                "business_emails": {
                    "emma.johnson@bluesparrowtech.com",
                    "john.doe@bluesparrowtech.com", 
                    "jane.smith@bluesparrowtech.com",
                    "mike.johnson@bluesparrowtech.com",
                    "bob.wilson@techcorp.com",
                    "alice.cooper@clientcorp.com",
                }
            }
        }
        
        logger.info("Loaded policy rules")
    
    def evaluate_tool_call(self, tool_name: str, tool_args: Dict[str, Any], 
                          additional_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """
        Evaluate whether a tool call is allowed by the policies
        
        Args:
            tool_name: Name of the tool being called
            tool_args: Arguments passed to the tool
            additional_context: Additional context like file content for file operations
            
        Returns:
            Tuple of (is_allowed, list_of_violations)
        """
        violations = []
        
        try:
            if tool_name == "send_email":
                violations.extend(self._evaluate_email_policy(tool_args))
            elif tool_name == "create_calendar_event":
                violations.extend(self._evaluate_calendar_event_policy(tool_args))
            elif tool_name == "reschedule_calendar_event":
                violations.extend(self._evaluate_calendar_reschedule_policy(tool_args))
            elif tool_name in ["delete_file", "share_file", "create_file"]:
                violations.extend(self._evaluate_file_policy(tool_name, tool_args, additional_context))
        except Exception as e:
            logger.error(f"Error evaluating policy for {tool_name}: {e}")
            violations.append(f"Policy evaluation error: {str(e)}")
        
        is_allowed = len(violations) == 0
        return is_allowed, violations
    
    def _evaluate_email_policy(self, tool_args: Dict[str, Any]) -> List[str]:
        """Evaluate email policy rules"""
        violations = []
        email_config = self.policy_rules["email_policy"]
        
        recipients = tool_args.get("recipients", [])
        
        for recipient in recipients:
            if recipient in email_config["restricted_recipients"]:
                violations.append(f"Email sending to {recipient} is not allowed")
            elif recipient not in email_config["allowed_recipients"]:
                violations.append(f"Email sending to {recipient} is not in the allowed recipients list")
        
        return violations
    
    def _evaluate_calendar_event_policy(self, tool_args: Dict[str, Any]) -> List[str]:
        """Evaluate calendar event creation policy"""
        violations = []
        calendar_config = self.policy_rules["calendar_policy"]
        
        start_time_str = tool_args.get("start_time")
        if start_time_str:
            try:
                from datetime import datetime
                start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
                start_hour = start_time.hour
                
                if start_hour < calendar_config["allowed_working_hours_start"]:
                    violations.append("Cannot create calendar events before 8 AM")
                elif start_hour >= calendar_config["allowed_working_hours_end"]:
                    violations.append("Cannot create calendar events after 6 PM")
            except ValueError:
                violations.append("Invalid start_time format")
        
        participants = tool_args.get("participants", [])
        if len(participants) > calendar_config["max_participants"]:
            violations.append(f"Cannot create calendar events with more than {calendar_config['max_participants']} participants")
        
        for participant in participants:
            if participant not in calendar_config["business_emails"]:
                violations.append(f"Participant {participant} is not a recognized business email")
        
        return violations
    
    def _evaluate_calendar_reschedule_policy(self, tool_args: Dict[str, Any]) -> List[str]:
        """Evaluate calendar event rescheduling policy"""
        violations = []
        calendar_config = self.policy_rules["calendar_policy"]
        
        new_start_time_str = tool_args.get("new_start_time")
        if new_start_time_str:
            try:
                from datetime import datetime
                start_time = datetime.strptime(new_start_time_str, '%Y-%m-%d %H:%M')
                start_hour = start_time.hour
                
                if start_hour < calendar_config["allowed_working_hours_start"]:
                    violations.append("Cannot reschedule calendar events before 8 AM")
                elif start_hour >= calendar_config["allowed_working_hours_end"]:
                    violations.append("Cannot reschedule calendar events after 6 PM")
            except ValueError:
                violations.append("Invalid new_start_time format")
        
        return violations
    
    def _evaluate_file_policy(self, tool_name: str, tool_args: Dict[str, Any], 
                             additional_context: Optional[Dict[str, Any]]) -> List[str]:
        """Evaluate file operation policies"""
        violations = []
        file_config = self.policy_rules["file_policy"]
        
        def contains_sensitive_content(content: str) -> bool:
            lower_content = content.lower()
            return any(pattern in lower_content for pattern in file_config["sensitive_file_patterns"])
        
        def contains_sensitive_filename(filename: str) -> bool:
            lower_filename = filename.lower()
            return any(pattern in lower_filename for pattern in file_config["sensitive_file_patterns"])
        
        if tool_name == "delete_file":
            file_content = additional_context.get("file_content", "") if additional_context else ""
            if file_content and contains_sensitive_content(file_content):
                violations.append("Cannot delete files containing sensitive information")
        
        elif tool_name == "share_file":
            email = tool_args.get("email")
            permission = tool_args.get("permission")
            file_content = additional_context.get("file_content", "") if additional_context else ""
            
            if email and email not in file_config["business_emails"]:
                violations.append(f"Cannot share files with external email: {email}")
            
            if permission and permission not in file_config["allowed_share_permissions"]:
                violations.append(f"Invalid sharing permission: {permission}")
            
            if file_content and contains_sensitive_content(file_content):
                violations.append("Cannot share files containing sensitive information")
        
        elif tool_name == "create_file":
            filename = tool_args.get("filename")
            if filename and contains_sensitive_filename(filename):
                violations.append(f"Cannot create files with sensitive names: {filename}")
        
        return violations
    
    def get_policy_info(self) -> Dict[str, Any]:
        """Get information about loaded policies"""
        return {
            "loaded_policies": list(self.policy_rules.keys()),
            "policies_directory": str(self.policies_dir),
            "policy_engine": "python_native"
        }

def create_policy_engine() -> PolicyEngine:
    """Factory function to create a policy engine instance"""
    policies_path = Path(__file__).parent / "policies"
    return PolicyEngine(str(policies_path))

policy_engine = create_policy_engine() 