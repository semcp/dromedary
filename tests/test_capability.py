#!/usr/bin/env python3

import unittest

from interpreter import PythonInterpreter
from capability import CapabilityValue, SourceType


class TestCapability(unittest.TestCase):

    def print_capability_info(self, name, cap_value):
        if isinstance(cap_value, CapabilityValue):
            print(f"{name} = {cap_value}")
            sources_info = [f"{s.type.value}({s.identifier})" if s.identifier else s.type.value for s in cap_value.capability.sources]
            print(f"  Sources: {sources_info}")
            print(f"  Dependencies: {len(cap_value.dependencies)}")
            print(f"  Value type: {type(cap_value.value).__name__}")
        else:
            print(f"{name} = {cap_value} (not a CapabilityValue)")

    def assert_capability_value(self, var_name, cap_value, expected_sources=None, min_dependencies=None):
        self.assertIsInstance(cap_value, CapabilityValue, f"{var_name} should be a CapabilityValue, got {type(cap_value)}")
        
        if expected_sources:
            actual_source_types = [s.type for s in cap_value.capability.sources]
            for expected_source in expected_sources:
                self.assertIn(expected_source, actual_source_types, f"{var_name} should have {expected_source} source, got {actual_source_types}")
        
        if min_dependencies is not None:
            self.assertGreaterEqual(len(cap_value.dependencies), min_dependencies, f"{var_name} should have at least {min_dependencies} dependencies, got {len(cap_value.dependencies)}")

    def test_basic_capabilities(self):
        print("Testing basic capability tracking...")
        
        code = """
x = 42
y = "hello"
z = x + 10
result = f"{y} world, number is {z}"
result
"""
        
        interpreter = PythonInterpreter()
        execution_result = interpreter.execute(code)
        self.assertTrue(execution_result['success'], f"Execution should succeed: {execution_result['error']}")
        
        self.assertIn('x', interpreter.globals, "Variable 'x' should exist")
        x_val = interpreter.globals['x']
        self.assert_capability_value('x', x_val, expected_sources=[SourceType.USER], min_dependencies=0)
        
        self.assertIn('result', interpreter.globals, "Variable 'result' should exist")
        result_val = interpreter.globals['result']
        self.assert_capability_value('result', result_val, expected_sources=[SourceType.SYSTEM, SourceType.USER], min_dependencies=1)
        
        print("✅ Basic capability test passed!")

    def test_tool_capabilities(self):
        print("\n\nTesting tool capability tracking...")
        
        code = """
files = list_files()
first_file = files[0] if files else None
first_file
"""
        
        interpreter = PythonInterpreter()
        execution_result = interpreter.execute(code)
        self.assertTrue(execution_result['success'], f"Execution should succeed: {execution_result['error']}")
        
        self.assertIn('files', interpreter.globals, "files does not exist")
        files_val = interpreter.globals['files']
        self.assert_capability_value('files', files_val, expected_sources=[SourceType.TOOL], min_dependencies=0)
        self.assertIsInstance(files_val.value, list, f"files should be a list, got {type(files_val.value)}")
                
        self.assertIn('first_file', interpreter.globals, "first_file does not exist")
        first_file_val = interpreter.globals['first_file']
        self.assert_capability_value('first_file', first_file_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)
        
        print("✅ Tool capability test passed!")

    def test_complex_email_workflow(self):
        print("\n\nTesting complex email workflow capability tracking...")
        print("This demonstrates the capability flow from the prompt1.md example...")
        
        code = """
received = get_received_emails()
last_email = received[-1]
body_text = last_email.body

class BobEmail(BaseModel):
    email: EmailStr

parsed = query_ai_assistant(
    f\"\"\"Extract Bob's email address from the following text. Only return the email address that belongs to Bob:

\\\"\\\"\\\"
{body_text}
\\\"\\\"\\\"
\"\"\",
    output_schema=BobEmail
)

bob_email = parsed.email

today_iso = get_current_day()
today_date = datetime.fromisoformat(today_iso)
tomorrow_date = today_date + timedelta(days=1)
tomorrow_iso = tomorrow_date.isoformat()

subject = "Reminder: Tomorrow's meeting"
body = (
    f"Hi Bob,\\n\\n"
    f"This is a friendly reminder of our meeting scheduled for {tomorrow_iso}.\\n\\n"
    f"Best regards,\\n"
    f"Emma Johnson"
)

send_email(
    recipients=[bob_email],
    subject=subject,
    body=body
)

print("Email workflow completed!")
"""
        
        interpreter = PythonInterpreter()
        execution_result = interpreter.execute(code)
        self.assertTrue(execution_result['success'], f"Execution should succeed: {execution_result['error']}")
            
        self.assertIn('received', interpreter.globals, "received does not exist")
        received_val = interpreter.globals['received']
        self.assert_capability_value('received', received_val, expected_sources=[SourceType.TOOL], min_dependencies=0)

        self.assertIn('last_email', interpreter.globals, "last_email does not exist")
        last_email_val = interpreter.globals['last_email']
        self.assert_capability_value('last_email', last_email_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)

        self.assertIn('body_text', interpreter.globals, "body_text does not exist")
        body_text_val = interpreter.globals['body_text']
        self.assert_capability_value('body_text', body_text_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)

        self.assertIn('parsed', interpreter.globals, "parsed does not exist")
        parsed_val = interpreter.globals['parsed']
        self.assert_capability_value('parsed', parsed_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)
            
        self.assertIn('bob_email', interpreter.globals, "bob_email does not exist")
        bob_email_val = interpreter.globals['bob_email']
        self.assert_capability_value('bob_email', bob_email_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)

        self.assertIn('today_iso', interpreter.globals, "today_iso does not exist")
        today_iso_val = interpreter.globals['today_iso']
        self.assert_capability_value('today_iso', today_iso_val, expected_sources=[SourceType.TOOL], min_dependencies=0)
            
        self.assertIn('today_date', interpreter.globals, "today_date does not exist")
        today_date_val = interpreter.globals['today_date']
        self.assert_capability_value('today_date', today_date_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)
                
        self.assertIn('tomorrow_date', interpreter.globals, "tomorrow_date does not exist")
        tomorrow_date_val = interpreter.globals['tomorrow_date']
        self.assert_capability_value('tomorrow_date', tomorrow_date_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)
                
        self.assertIn('tomorrow_iso', interpreter.globals, "tomorrow_iso does not exist")
        tomorrow_iso_val = interpreter.globals['tomorrow_iso']
        self.assert_capability_value('tomorrow_iso', tomorrow_iso_val, expected_sources=[SourceType.SYSTEM, SourceType.TOOL], min_dependencies=1)
            
        self.assertIn('subject', interpreter.globals, "subject does not exist")
        subject_val = interpreter.globals['subject']
        self.assert_capability_value('subject', subject_val, expected_sources=[SourceType.USER], min_dependencies=0)
                
        self.assertIn('body', interpreter.globals, "body does not exist")
        body_val = interpreter.globals['body']
        self.assert_capability_value('body', body_val, expected_sources=[SourceType.SYSTEM, SourceType.USER, SourceType.TOOL], min_dependencies=1)


if __name__ == "__main__":
    unittest.main() 