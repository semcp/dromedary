The following is a simple example of how the capability source tagging works.

## Code

```python

received = get_received_emails()
# source: [Tool(get_received_emails)]
last_email = received[-1]
# source: [Tool(get_received_emails)] inherited from get_received_emails

body_text = last_email.body
# source: [Tool(get_received_emails)] inherited from get_received_emails


class BobEmail(BaseModel):
    email: EmailStr

parsed = query_ai_assistant(
    f"""Extract Bob's email address from the following text. Only return the email address that belongs to Bob:

\"\"\"
{body_text}
\"\"\"""",
    output_schema=BobEmail
)
# source: [CaMeL, Tool(get_received_emails)]

bob_email = parsed.email
# source: [CaMeL, Tool(get_received_emails)]

# Compute tomorrow's date
today_iso = get_current_day()                       # e.g. "2024-06-15"
# source: [Tool(get_current_day)]
today_date = datetime.fromisoformat(today_iso)
# source: [CaMeL, Tool(get_current_day)]
tomorrow_date = today_date + timedelta(days=1)
# source: [CaMeL, Tool(get_current_day)]
tomorrow_iso = tomorrow_date.isoformat()             # e.g. "2024-06-16"
# source: [CaMeL, Tool(get_current_day)]

# Send the reminder
subject = "Reminder: Tomorrow's meeting"
# source: [User]
body = (
    f"Hi Bob,\n\n"
    f"This is a friendly reminder of our meeting scheduled for {tomorrow_iso}.\n\n"
    f"Best regards,\n"
    f"Emma Johnson"
)
# source: [User, CaMeL, Tool(get_current_day)]

send_email(
    recipients=[bob_email],
    subject=subject,
    body=body
)

## control and data graph 
# <get_received_emails() <- received <- last_email <- body_text <- parsed>
# <query_ai_assistant() <- parsed <- bob_email>
# <get_current_day() <- today_iso <- today_date <- tomorrow_date <- tomorrow_iso <- body <- send_email()>>
# <bob_email <- send_email()>
```