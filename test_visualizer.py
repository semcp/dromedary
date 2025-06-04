#!/usr/bin/env python3

from visualizer import InterpreterVisualized
from interpreter import PythonInterpreter

def test():
    interpreter_with_viz = InterpreterVisualized(PythonInterpreter, enable_policies=False)
    
    test_code = """
from pydantic import BaseModel, EmailStr

# Schema for extracting Bob's email address
class ExtractEmail(BaseModel):
    email: EmailStr

# Get the most recent received email
received = get_received_emails()
last_email = received[-1]

# Extract Bob's email address from the last email
extracted = query_ai_assistant(
    f"Extract Bob's email address from the following email:\\n\\n"
    f"Subject: {last_email.subject}\\n\\n"
    f"Body:\\n{last_email.body}",
    ExtractEmail
)
bob_email = extracted.email

# Send the reminder email
reminder = send_email(
    recipients=[bob_email],
    subject="Reminder: Tomorrow's Meeting",
    body=(
        "Hi Bob,\\n\\n"
        "This is a friendly reminder about our meeting scheduled for tomorrow.\\n\\n"
        "Looking forward to speaking with you.\\n\\n"
        "Best,\\n"
        "Emma"
    )
)

reminder
"""

    try:
        result = interpreter_with_viz.execute(test_code)
        
        if result["success"]:
            interpreter_with_viz.visualize()
        else:
            print(f"❌ Execution failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":    
    test()