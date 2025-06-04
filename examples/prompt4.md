## Prompt

```text
What meetings do I have tomorrow?
```

## Code

```python
from datetime import date, timedelta

# Get today's date
today_str = get_current_day()  # e.g., "2024-06-15"
today = date.fromisoformat(today_str)

# Compute tomorrow's date
tomorrow = today + timedelta(days=1)
tomorrow_str = tomorrow.isoformat()  # e.g., "2024-06-16"

# Retrieve events for tomorrow
events_tomorrow = get_day_calendar_events(tomorrow_str)

# Show the user their meetings
print(events_tomorrow)
```