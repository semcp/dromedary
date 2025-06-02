package calendar.policy

import rego.v1

allowed_working_hours_start := 8
allowed_working_hours_end := 18

max_participants := 10

business_emails := {
    "emma.johnson@bluesparrowtech.com",
    "john.doe@bluesparrowtech.com", 
    "jane.smith@bluesparrowtech.com",
    "mike.johnson@bluesparrowtech.com",
    "bob.wilson@techcorp.com",
    "alice.cooper@clientcorp.com",
}

allow_create_calendar_event if {
    input.tool_name == "create_calendar_event"
    input.arguments.start_time
    start_hour := time.parse_rfc3339(input.arguments.start_time).hour
    start_hour >= allowed_working_hours_start
    start_hour < allowed_working_hours_end
    count(input.arguments.participants) <= max_participants
    every participant in input.arguments.participants {
        participant in business_emails
    }
}

allow_create_calendar_event if {
    input.tool_name != "create_calendar_event"
}

allow_reschedule_calendar_event if {
    input.tool_name == "reschedule_calendar_event"
    input.arguments.new_start_time
    start_hour := time.parse_rfc3339(input.arguments.new_start_time).hour
    start_hour >= allowed_working_hours_start
    start_hour < allowed_working_hours_end
}

allow_reschedule_calendar_event if {
    input.tool_name != "reschedule_calendar_event"
}

violation[msg] if {
    input.tool_name == "create_calendar_event"
    input.arguments.start_time
    start_hour := time.parse_rfc3339(input.arguments.start_time).hour
    start_hour < allowed_working_hours_start
    msg := "Cannot create calendar events before 8 AM"
}

violation[msg] if {
    input.tool_name == "create_calendar_event"
    input.arguments.start_time
    start_hour := time.parse_rfc3339(input.arguments.start_time).hour
    start_hour >= allowed_working_hours_end
    msg := "Cannot create calendar events after 6 PM"
}

violation[msg] if {
    input.tool_name == "create_calendar_event"
    count(input.arguments.participants) > max_participants
    msg := sprintf("Cannot create calendar events with more than %d participants", [max_participants])
}

violation[msg] if {
    input.tool_name == "create_calendar_event"
    some participant in input.arguments.participants
    not participant in business_emails
    msg := sprintf("Participant %s is not a recognized business email", [participant])
} 