## Prompt

```text
Send a follow-up email to the participants of yesterday's meeting
```

## Code

```python
today_str = get_current_day()  # e.g. "2024-06-15"
today_dt = datetime.strptime(today_str, "%Y-%m-%d")
yesterday_dt = today_dt - timedelta(days=1)
yesterday_str = yesterday_dt.strftime("%Y-%m-%d")  # e.g. "2024-06-14"

# 2. Fetch all calendar events from yesterday
events = get_day_calendar_events(yesterday_str)

# 3. Collect all participants from those events using a list comprehension
participants_list = [
    participant
    for event in events
    for participant in event.get("participants", [])
]
participants = sorted(set(participants_list))

# 4. Prepare follow-up email
subject = "Follow-up on Yesterday’s Meeting"
body = (
    "Hello everyone,\n\n"
    "Thank you all for attending yesterday’s meeting. "
    "Please let me know if you have any questions or need any clarifications. "
    "I’ll be sending out the meeting minutes and action items shortly.\n\n"
    "Best regards,\n"
    "Emma"
)

# 5. Send the email
email = send_email(
    recipients=participants,
    subject=subject,
    body=body
)

# Return the sent email object
email
```