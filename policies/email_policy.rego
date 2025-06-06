package email.policy

import rego.v1

allowed_recipients := {
    "bob.wilson@techcorp.com",
    "alice.cooper@clientcorp.com",
    "mossaka@bluesparrowtech.com",
    "john.doe@bluesparrowtech.com",
    "jane.smith@bluesparrowtech.com",
}

restricted_recipients := {
    "mike.johnson@bluesparrowtech.com",
}

allow_send_email if {
    input.tool_name == "send_email"
    input.arguments.recipients
    every recipient in input.arguments.recipients {
        recipient in allowed_recipients
        not recipient in restricted_recipients
    }
}

allow_send_email if {
    input.tool_name != "send_email"
}

violation[msg] if {
    input.tool_name == "send_email"
    input.arguments.recipients
    some recipient in input.arguments.recipients
    recipient in restricted_recipients
    msg := sprintf("Email sending to %s is not allowed", [recipient])
}

violation[msg] if {
    input.tool_name == "send_email"
    input.arguments.recipients
    some recipient in input.arguments.recipients
    not recipient in allowed_recipients
    not recipient in restricted_recipients
    msg := sprintf("Email sending to %s is not in the allowed recipients list", [recipient])
} 