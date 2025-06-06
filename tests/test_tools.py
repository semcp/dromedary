import unittest
from datetime import datetime
from tools import (
    SendEmailTool, GetCurrentDayTool, CreateCalendarEventTool, 
    CreateFileTool, SearchContactsByNameTool
)


class TestTools(unittest.TestCase):

    def test_get_current_day_tool(self):
        tool = GetCurrentDayTool()
        current_day = tool._run()
        
        self.assertIsInstance(current_day, str)
        self.assertRegex(current_day, r'\d{4}-\d{2}-\d{2}')
        
        datetime.strptime(current_day, '%Y-%m-%d')

    def test_search_contacts_tool(self):
        tool = SearchContactsByNameTool()
        contacts = tool._run("Mossaka")
        
        self.assertIsInstance(contacts, list)
        self.assertGreater(len(contacts), 0)
        
        for contact in contacts:
            self.assertIn("Mossaka", contact.name)
            self.assertIsInstance(contact.email, str)
            self.assertIn("@", contact.email)

    def test_create_file_tool(self):
        tool = CreateFileTool()
        filename = "test-document.txt"
        content = "This is a test document created by P-LLM."
        
        file = tool._run(filename, content)
        
        self.assertEqual(file.filename, filename)
        self.assertEqual(file.content, content)
        self.assertIsInstance(file.id_, str)
        self.assertEqual(file.owner, "mossaka@bluesparrowtech.com")
        self.assertGreater(file.size, 0)

    def test_send_email_tool(self):
        tool = SendEmailTool()
        recipients = ["john.doe@bluesparrowtech.com"]
        subject = "Test Email from P-LLM"
        body = "This is a test email sent by the P-LLM agent system."
        
        email = tool._run(recipients=recipients, subject=subject, body=body)
        
        self.assertEqual(email.recipients, recipients)
        self.assertEqual(email.subject, subject)
        self.assertEqual(email.body, body)
        self.assertEqual(email.sender, "mossaka@bluesparrowtech.com")
        self.assertIsInstance(email.id_, str)

    def test_create_calendar_event_tool(self):
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
        tool = SearchContactsByNameTool()
        contacts = tool._run("NonExistentName")
        
        self.assertIsInstance(contacts, list)
        self.assertEqual(len(contacts), 0)

    def test_email_with_cc_bcc(self):
        tool = SendEmailTool()
        recipients = ["john.doe@bluesparrowtech.com"]
        cc = ["jane.smith@bluesparrowtech.com"]
        bcc = ["mossaka@bluesparrowtech.com"]
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