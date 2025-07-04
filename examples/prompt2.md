## Prompt

```text
Check my unread emails and summarize the important ones
```

## Code

```python
# Fetch unread emails
emails = get_unread_emails()

if not emails:
    print("You have no unread emails.")
else:
    # Build the text block for analysis without using augmented assignments
    text_pieces = [
        "Email " + str(idx) + ":\n"
        + "Sender: " + email.sender + "\n"
        + "Subject: " + email.subject + "\n"
        + "Body: " + email.body + "\n\n"
        for idx, email in enumerate(emails, start=1)
    ]
    emails_text = "".join(text_pieces)

    # Schema for each important email
    class ImportantEmail(BaseModel):
        sender: EmailStr
        subject: str
        summary: str

    # Schema for the overall output
    class SummaryOutput(BaseModel):
        important_emails: list[ImportantEmail]

    # Ask the AI assistant to identify and summarize the important emails
    result = query_ai_assistant(
        (
            "You are given a list of emails. Identify which emails are important—i.e., "
            "require action or contain critical information—and provide a concise summary "
            "of each. Exclude any emails that do not need action. "
            "Return a JSON object with a field `important_emails` that is a list of objects "
            "with `sender`, `subject`, and `summary`.\n\n"
        )
        + emails_text,
        output_schema=SummaryOutput
    )

    # Output the summaries of important emails
    print(result.important_emails)
```