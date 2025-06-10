# dromedary 🐪

Dromedary is a one-humped Camel. It is my replication of the CaMeL system from a Google DeepMind's paper [_Defeating Prompt Injections by Design_](https://arxiv.org/pdf/2503.18813).

> :construction: Warning: This project is still in the early stage of development. Many aspects of the system are not yet implemented. Please see the [What's missing?](#whats-missing) section for more details.


https://github.com/user-attachments/assets/978103b7-d87e-4c08-a89b-762717b21c79


## What's the point of this project?

I want to build a secure agent runtime that can mitigate the risk of prompt injection attack. I truly believe that the authors of the CaMeL paper is right about that traditional software security practices can provide a good defense against it. Thus I want to build a replication of the system to see if it can work.


## How to run?

At the moment, this project only supports Azure OpenAI models. You need to set the `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` environment variables.

```bash
export AZURE_OPENAI_ENDPOINT=https://<your-endpoint>.openai.azure.com/
export AZURE_OPENAI_API_KEY=<your-api-key>
```

Then you can run the project as simple as:

```bash
make run
```

## Example

One of the biggest value of this project is that it has a runtime for executing Agent's plan. This gives us a chance to closely see how the tools are used and in what order will the tools be used. It will also give us the flexibility to add taint analysis, RBAC etc. to the system to make it more secure. The following examples shows how the system is able to track data provenance and control flow and enforce security policies to disallow the agent from sending email to an untrusted source.

```console
👤 Mossaka: policy
🔒 Security policy enabled

👤 Mossaka: Find Bob's email in my last email and send him a reminder of tomorrow's meeting.
╭───────────────────────────────────────────────────────────────────────────────────────── 🤖 Plan ─────────────────────────────────────────────────────────────────────────────────────────╮
| from pydantic import BaseModel, EmailStr                                                                                                                                                  |
|                                                                                                                                                                                           |
| # Schema for extracting Bob's email address                                                                                                                                               |
| class ExtractEmail(BaseModel):                                                                                                                                                            |
|     email: EmailStr                                                                                                                                                                       |
|                                                                                                                                                                                           |
| # Get the most recent received email                                                                                                                                                      |
| received = get_received_emails()                                                                                                                                                          |
| last_email = received[-1]                                                                                                                                                                 |
|                                                                                                                                                                                           |
| # Extract Bob's email address from the last email                                                                                                                                         |
| extracted = query_ai_assistant(                                                                                                                                                           |
|     f"Extract Bob's email address from the following email:\n\n"                                                                                                                          |
|     f"Subject: {last_email.subject}\n\n"                                                                                                                                                  |
|     f"Body:\n{last_email.body}",                                                                                                                                                         |
|     ExtractEmail                                                                                                                                                                          |
| )                                                                                                                                                                                         |
| bob_email = extracted.email                                                                                                                                                               |
|                                                                                                                                                                                           |
| # Send the reminder email                                                                                                                                                                 |
| reminder = send_email(                                                                                                                                                                    |
|     recipients=[bob_email],                                                                                                                                                               |
|     subject="Reminder: Tomorrow's Meeting",                                                                                                                                               |
|     body=(                                                                                                                                                                                |
|         "Hi Bob,\n\n"                                                                                                                                                                     |
|         "This is a friendly reminder about our meeting scheduled for tomorrow.\n\n"                                                                                                       |
|         "Looking forward to speaking with you.\n\n"                                                                                                                                       |
|         "Best,\n"                                                                                                                                                                         |
|         "Mossaka"                                                                                                                                                                         |
|     )                                                                                                                                                                                     |
| )                                                                                                                                                                                         |
| reminder                                                                                                                                                                                  |
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
========================================
🚫 POLICY VIOLATION: Policy violation for send_email: Cannot send email to address from untrusted source 'get_received_emails'. Use the search_contacts_by_name or search_contacts_by_email tools to get the email address.

👤 Mossaka: find bob's email by search bob wilson and send him a reminder of tomorrow's meeting
╭───────────────────────────────────────────────────────────────────────────────────────── 🤖 Plan ─────────────────────────────────────────────────────────────────────────────────────────╮
|from pydantic import BaseModel, EmailStr                                                                                                                                                   |
|                                                                                                                                                                                           |
|# Search contacts for Bob Wilson                                                                                                                                                           |
|contacts = search_contacts_by_name("Bob Wilson")                                                                                                                                           |
|# Take the first matching contact                                                                                                                                                          |
|bob_contact = contacts[0]                                                                                                                                                                  |
|bob_email = bob_contact.email                                                                                                                                                              |
|                                                                                                                                                                                           |
|# Send the reminder email                                                                                                                                                                  |
|reminder = send_email(                                                                                                                                                                     |
|    recipients=[bob_email],                                                                                                                                                                |
|    subject="Reminder: Tomorrow's Meeting",                                                                                                                                                |
|    body=(                                                                                                                                                                                 |
|        "Hi Bob,\n\n"                                                                                                                                                                      |
|        "This is a friendly reminder about our meeting scheduled for tomorrow.\n\n"                                                                                                        |
|        "Looking forward to speaking with you.\n\n"                                                                                                                                        |
|        "Best,\n"                                                                                                                                                                          |
|        "Mossaka"                                                                                                                                                                          |
|    )                                                                                                                                                                                      |
|)                                                                                                                                                                                          |
|reminder                                                                                                                                                                                   |
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
========================================
Reminder: Tomorrow's Meeting | To: bob.wilson@techcorp.com | 2025-06-05 22:07

👤 Mossaka: ^C
👋 Goodbye Mossaka!
```

### The Data and Control Flow Graph

![Data and Control Flow Graph](./images/graph.png)

## Components

It contains a few components:

1. P-LLM Agent: A langgraph agent with tools that can only be used for planning. It's plan is written as a Python code and will be executed by a custom Python interpreter. The design constraint is that the agent can only see trusted data, i.e. user prompt or user verified data.
2. A special tool called `query_ai_assistant` that can be used to query a chatbot for string manipulation. The chatbot has no access to tools, and thus cannot affect the real world. Some string manipulation includes understanding the email content and find some important information that the P-LLM Agent needs.
3. A policy engine to enforce security policies at runtime. The current design of the policies are hardcoded in Python, but in the future, I would like to use Rego to write the policies and use Open Policy Agent as the policy engine for enforcing policies at runtime.
4. A custom Python interpreter to execute the Python code written by the P-LLM Agent.
5. Tools to interact with the real world. currently the tools are written in Python. My goal is to use Model Context Protocol for tool definitions.

## What's missing?

- I need to implement the full RBAC system for the interpreter.
- Integration with MCP for tool definitions.
- I want the Python interpreter to be performant and robust. This could be a challenge if it's written in Python. One idea is to use Rust to write the interpreter.
