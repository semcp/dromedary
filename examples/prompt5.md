## Prompt

```text
Can you send bob the document named meeting notes he requested? bob's email can be found in my last email      
```

## Code

```python
# Retrieve all received emails and get the last one
received = get_received_emails()
last_email = received[-1]

# Extract Bob's email address from the body of the last email
from pydantic import BaseModel, EmailStr

class ExtractEmail(BaseModel):
    email: EmailStr

extraction = query_ai_assistant(
    f"Extract the first email address found in the following text:\n\n{last_email.body}",
    ExtractEmail
)
bob_email = extraction.email

# Locate the file named "meeting notes"; if none found by name, search by content
files_by_name = search_files_by_filename("meeting notes")
if files_by_name:
    file_to_send = files_by_name[0]
else:
    files_by_content = search_files("meeting notes")
    file_to_send = files_by_content[0]

# Send Bob the document as an attachment (using the file ID string)
sent_email = send_email(
    recipients=[bob_email],
    subject="Meeting Notes",
    body=(
        "Hi Bob,\n\n"
        "Please find attached the meeting notes as requested.\n\n"
        "Best,\n"
        "Emma"
    ),
    attachments=[file_to_send.id_]
)

print(f"Sent meeting notes to {bob_email}")
sent_email
```