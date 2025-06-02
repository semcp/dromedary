"""
Test script to demonstrate P-LLM tools functionality
"""

import unittest
from datetime import datetime
from tools import (
    SendEmailTool, GetCurrentDayTool, CreateCalendarEventTool, 
    CreateFileTool, SearchContactsByNameTool
)


class TestTools(unittest.TestCase):
    """Test cases for P-LLM tools"""

    def test_get_current_day_tool(self):
        """Test GetCurrentDayTool returns a valid date string"""
        tool = GetCurrentDayTool()
        current_day = tool._run()
        
        self.assertIsInstance(current_day, str)
        self.assertRegex(current_day, r'\d{4}-\d{2}-\d{2}')
        
        # Verify it's a valid date by parsing it
        datetime.strptime(current_day, '%Y-%m-%d')

    def test_search_contacts_tool(self):
        """Test SearchContactsByNameTool finds contacts correctly"""
        tool = SearchContactsByNameTool()
        contacts = tool._run("Emma")
        
        self.assertIsInstance(contacts, list)
        self.assertGreater(len(contacts), 0)
        
        # Check that all returned contacts have Emma in their name
        for contact in contacts:
            self.assertIn("Emma", contact.name)
            self.assertIsInstance(contact.email, str)
            self.assertIn("@", contact.email)

    def test_create_file_tool(self):
        """Test CreateFileTool creates files correctly"""
        tool = CreateFileTool()
        filename = "test-document.txt"
        content = "This is a test document created by P-LLM."
        
        file = tool._run(filename, content)
        
        self.assertEqual(file.filename, filename)
        self.assertEqual(file.content, content)
        self.assertIsInstance(file.id_, str)
        self.assertEqual(file.owner, "emma.johnson@bluesparrowtech.com")
        self.assertGreater(file.size, 0)

    def test_send_email_tool(self):
        """Test SendEmailTool sends emails correctly"""
        tool = SendEmailTool()
        recipients = ["john.doe@bluesparrowtech.com"]
        subject = "Test Email from P-LLM"
        body = "This is a test email sent by the P-LLM agent system."
        
        email = tool._run(recipients=recipients, subject=subject, body=body)
        
        self.assertEqual(email.recipients, recipients)
        self.assertEqual(email.subject, subject)
        self.assertEqual(email.body, body)
        self.assertEqual(email.sender, "emma.johnson@bluesparrowtech.com")
        self.assertIsInstance(email.id_, str)

    def test_create_calendar_event_tool(self):
        """Test CreateCalendarEventTool creates events correctly"""
        tool = CreateCalendarEventTool()
        title = "P-LLM Test Meeting"
        tomorrow = datetime.now().strftime('%Y-%m-%d')
        start_time = f"{tomorrow} 14:00"
        end_time = f"{tomorrow} 15:00"
        description = "A test meeting created by P-LLM"
        participants = ["jane.smith@bluesparrowtech.com"]
        location = "Conference Room A"
        
        event = tool._run(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            participants=participants,
            location=location
        )
        
        self.assertEqual(event.title, title)
        self.assertEqual(event.description, description)
        self.assertEqual(event.participants, participants)
        self.assertEqual(event.location, location)
        self.assertIsInstance(event.id_, str)

    def test_search_contacts_empty_query(self):
        """Test SearchContactsByNameTool with non-existent name"""
        tool = SearchContactsByNameTool()
        contacts = tool._run("NonExistentName")
        
        self.assertIsInstance(contacts, list)
        self.assertEqual(len(contacts), 0)

    def test_email_with_cc_bcc(self):
        """Test SendEmailTool with CC and BCC recipients"""
        tool = SendEmailTool()
        recipients = ["john.doe@bluesparrowtech.com"]
        cc = ["jane.smith@bluesparrowtech.com"]
        bcc = ["emma.johnson@bluesparrowtech.com"]
        subject = "Test Email with CC/BCC"
        body = "Testing CC and BCC functionality."
        
        email = tool._run(
            recipients=recipients,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc
        )
        
        self.assertEqual(email.recipients, recipients)
        self.assertEqual(email.cc, cc)
        self.assertEqual(email.bcc, bcc)
        self.assertEqual(email.subject, subject)
        self.assertEqual(email.body, body)

    def test_file_creation_with_different_extensions(self):
        """Test CreateFileTool with different file extensions"""
        tool = CreateFileTool()
        
        test_files = [
            ("document.txt", "Plain text content"),
            ("data.json", '{"key": "value"}'),
            ("script.py", "print('Hello, World!')"),
        ]
        
        for filename, content in test_files:
            with self.subTest(filename=filename):
                file = tool._run(filename, content)
                self.assertEqual(file.filename, filename)
                self.assertEqual(file.content, content)
                self.assertGreater(file.size, 0)


if __name__ == "__main__":
    unittest.main() 