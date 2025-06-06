package file.policy

import rego.v1

sensitive_file_patterns := [
    "confidential",
    "secret",
    "private",
    "password",
    "key"
]

allowed_share_permissions := {
    "read",
    "write"
}

business_emails := {
    "mossaka@bluesparrowtech.com",
    "john.doe@bluesparrowtech.com", 
    "jane.smith@bluesparrowtech.com",
    "mike.johnson@bluesparrowtech.com",
    "bob.wilson@techcorp.com",
    "alice.cooper@clientcorp.com",
}

allow_delete_file if {
    input.tool_name == "delete_file"
    input.file_content
    not contains_sensitive_content(input.file_content)
}

allow_delete_file if {
    input.tool_name != "delete_file"
}

allow_share_file if {
    input.tool_name == "share_file"
    input.arguments.email in business_emails
    input.arguments.permission in allowed_share_permissions
    input.file_content
    not contains_sensitive_content(input.file_content)
}

allow_share_file if {
    input.tool_name != "share_file"
}

allow_create_file if {
    input.tool_name == "create_file"
    input.arguments.filename
    not contains_sensitive_filename(input.arguments.filename)
}

allow_create_file if {
    input.tool_name != "create_file"
}

contains_sensitive_content(content) if {
    lower_content := lower(content)
    some pattern in sensitive_file_patterns
    contains(lower_content, pattern)
}

contains_sensitive_filename(filename) if {
    lower_filename := lower(filename)
    some pattern in sensitive_file_patterns
    contains(lower_filename, pattern)
}

violation[msg] if {
    input.tool_name == "delete_file"
    input.file_content
    contains_sensitive_content(input.file_content)
    msg := "Cannot delete files containing sensitive information"
}

violation[msg] if {
    input.tool_name == "share_file"
    input.arguments.email
    not input.arguments.email in business_emails
    msg := sprintf("Cannot share files with external email: %s", [input.arguments.email])
}

violation[msg] if {
    input.tool_name == "share_file"
    input.arguments.permission
    not input.arguments.permission in allowed_share_permissions
    msg := sprintf("Invalid sharing permission: %s", [input.arguments.permission])
}

violation[msg] if {
    input.tool_name == "share_file"
    input.file_content
    contains_sensitive_content(input.file_content)
    msg := "Cannot share files containing sensitive information"
}

violation[msg] if {
    input.tool_name == "create_file"
    input.arguments.filename
    contains_sensitive_filename(input.arguments.filename)
    msg := sprintf("Cannot create files with sensitive names: %s", [input.arguments.filename])
} 