#!/usr/bin/env python3

import unittest
from policy_engine import policy_engine, PolicyViolationError
from interpreter import PythonInterpreter


class TestPolicies(unittest.TestCase):
    """Test cases for the policy engine"""

    def test_email_policies_allowed_recipients(self):
        """Test that emails to allowed recipients pass policy checks"""
        args = {
            "recipients": ["bob.wilson@techcorp.com", "alice.cooper@clientcorp.com"],
            "subject": "Test email",
            "body": "This is a test"
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("send_email", args)
        self.assertTrue(is_allowed)
        self.assertEqual(violations, [])

    def test_email_policies_blocked_recipients(self):
        """Test that emails to blocked recipients fail policy checks"""
        args = {
            "recipients": ["mike.johnson@bluesparrowtech.com"],
            "subject": "Test email",
            "body": "This is a test"
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("send_email", args)
        self.assertFalse(is_allowed)
        self.assertGreater(len(violations), 0)

    def test_email_policies_unauthorized_recipients(self):
        """Test that emails to unauthorized external recipients fail policy checks"""
        args = {
            "recipients": ["external@hacker.com"],
            "subject": "Test email", 
            "body": "This is a test"
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("send_email", args)
        self.assertFalse(is_allowed)
        self.assertGreater(len(violations), 0)

    def test_calendar_policies_business_hours(self):
        """Test that calendar events during business hours are allowed"""
        args = {
            "title": "Team Meeting",
            "start_time": "2024-01-15 14:00",
            "end_time": "2024-01-15 15:00",
            "description": "Weekly sync",
            "participants": ["bob.wilson@techcorp.com", "alice.cooper@clientcorp.com"]
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("create_calendar_event", args)
        self.assertTrue(is_allowed)
        self.assertEqual(violations, [])

    def test_calendar_policies_early_hours(self):
        """Test that calendar events too early are blocked"""
        args = {
            "title": "Early Meeting",
            "start_time": "2024-01-15 06:00",
            "end_time": "2024-01-15 07:00",
            "description": "Too early",
            "participants": ["bob.wilson@techcorp.com"]
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("create_calendar_event", args)
        self.assertFalse(is_allowed)
        self.assertGreater(len(violations), 0)

    def test_calendar_policies_too_many_participants(self):
        """Test that calendar events with too many participants are blocked"""
        args = {
            "title": "Large Meeting",
            "start_time": "2024-01-15 14:00",
            "end_time": "2024-01-15 15:00",
            "description": "Too many people",
            "participants": [f"user{i}@example.com" for i in range(15)]
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("create_calendar_event", args)
        self.assertFalse(is_allowed)
        self.assertGreater(len(violations), 0)

    def test_file_policies_normal_creation(self):
        """Test that normal file creation is allowed"""
        args = {
            "filename": "meeting_notes.txt",
            "content": "Today we discussed the quarterly reports"
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("create_file", args)
        self.assertTrue(is_allowed)
        self.assertEqual(violations, [])

    def test_file_policies_sensitive_creation(self):
        """Test that sensitive file creation is blocked"""
        args = {
            "filename": "confidential_passwords.txt",
            "content": "These are sensitive passwords"
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("create_file", args)
        self.assertFalse(is_allowed)
        self.assertGreater(len(violations), 0)

    def test_file_policies_external_sharing(self):
        """Test that sharing files with external users is blocked"""
        args = {
            "file_id": "file-123",
            "email": "external@hacker.com",
            "permission": "write"
        }
        is_allowed, violations = policy_engine.evaluate_tool_call("share_file", args)
        self.assertFalse(is_allowed)
        self.assertGreater(len(violations), 0)

    def test_interpreter_integration(self):
        """Test that the interpreter properly handles policy violations"""
        interpreter = PythonInterpreter()
        
        test_code = '''
result = send_email(
    recipients=["mike.johnson@bluesparrowtech.com"],
    subject="Test",
    body="This should be blocked"
)
result
'''
        
        result = interpreter.execute(test_code)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "policy")
        self.assertIn("Policy violation", result["error"])


if __name__ == "__main__":
    unittest.main() 