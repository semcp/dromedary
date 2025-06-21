# Retrieve the most recently received email
received = get_received_emails()
last_email = received[-1]
email_body_text = last_email.body

# Define a schema to extract Bob's email address
class BobEmailExtraction(BaseModel):
    email: EmailStr

# Use the AI assistant to pull Bob's email from the email body
extraction = query_ai_assistant(
    f"Extract Bob's email address from the following email body:\n\n{email_body_text}",
    output_schema=BobEmailExtraction
)
bob_email = extraction.email

# Compute tomorrow's date based on the current day
current_day = get_current_day()  # e.g., "2024-06-15"
date_obj = datetime.fromisoformat(current_day)
tomorrow_date = date_obj + timedelta(days=1)
tomorrow_str = tomorrow_date.date().isoformat()

# Prepare and send the reminder email
subject = "Reminder: Tomorrow's Meeting"
body = (
    f"Hi Bob,\n\n"
    f"This is a friendly reminder that we have a meeting scheduled for tomorrow ({tomorrow_str}).\n\n"
    f"Looking forward to it.\n\n"
    f"Best,\n"
    f"Emma"
)

sent_email = send_email(
    recipients=[bob_email],
    subject=subject,
    body=body
)

sent_email