# dromedary 🐪

Dromedary is a one-humped Camel. It is my replication of the CaMeL system from a Google DeepMind's paper [_Defeating Prompt Injections by Design_](https://arxiv.org/pdf/2503.18813).

> :construction: Warning: This project is still in the early stage of development. Many aspects of the system are not yet implemented. Please see the [What's missing?](#whats-missing) section for more details.

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

One of the biggest value of this project is that it has a runtime for executing Agent's plan. This gives us a chance to closely see how the tools are used and in what order will the tools be used. It will also give us the flexibility to add taint analysis, RBAC etc. to the system to make it more secure.

```console
👤 Emma: Find Bob's email in my last email and send him a reminder of tomorrow's meeting.
🤖 Assistant: 

... # omit the failed attempts

🔄 Agent retry code:
========================================
from datetime import date, timedelta
from pydantic import BaseModel, EmailStr

# Fetch all received emails and pick the last one
received = get_received_emails()
last_email = received[-1]
email_body = last_email.body

# Define a schema to extract Bob's email address
class ExtractBobEmail(BaseModel):
    bob_email: EmailStr

# Use the AI assistant to parse Bob's email from the last email's body
extraction = query_ai_assistant(
    f"Extract Bob's email address from the following text:\n\n{email_body}",
    ExtractBobEmail
)
bob_address = extraction.bob_email

# Compute tomorrow's date
today_iso = get_current_day()  # e.g. "2024-06-15"
today_date = date.fromisoformat(today_iso)
tomorrow_date = today_date + timedelta(days=1)
tomorrow_str = tomorrow_date.strftime("%Y-%m-%d")

# Prepare and send the reminder email
subject = f"Reminder: Meeting Tomorrow ({tomorrow_str})"
body = (
    f"Hi Bob,\n\n"
    f"This is a reminder for our meeting scheduled for tomorrow ({tomorrow_str}).\n\n"
    f"Best regards,\n"
    f"Emma"
)
sent_email = send_email(recipients=[bob_address], subject=subject, body=body)

# Show the result
print(sent_email)
========================================

id_='12cd18f7-15b7-422a-9036-6aa3befc1a8e' sender='emma.johnson@bluesparrowtech.com' recipients=['bob.wilson@techcorp.com'] cc=[] bcc=[] subject='Reminder: Meeting Tomorrow (2025-06-04)' body='Hi Bob,\n\nThis is a reminder for our meeting scheduled for tomorrow (2025-06-04).\n\nBest regards,\nEmma' status=<EmailStatus.sent: 'sent'> read=False timestamp=datetime.datetime(2025, 6, 3, 17, 22, 33, 822788) attachments=[]
```

It contains a few components:

1. P-LLM Agent: A langgraph agent with tools that can only be used for planning. It's plan is written as a Python code and will be executed by a custom Python interpreter. The design constraint is that the agent can only see trusted data, i.e. user prompt or user verified data.
2. A special tool called `query_ai_assistant` that can be used to query a chatbot for string manipulation. The chatbot has no access to tools, and thus cannot affect the real world. Some string manipulation includes understanding the email content and find some important information that the P-LLM Agent needs.
3. A policy engine to enforce security policies at runtime. The current design of the policies are hardcoded in Python, but in the future, I would like to use Rego to write the policies and use Open Policy Agent as the policy engine for enforcing policies at runtime.
4. A custom Python interpreter to execute the Python code written by the P-LLM Agent.
5. Tools to interact with the real world. currently the tools are written in Python. My goal is to use Model Context Protocol for tool definitions.

## What's missing?

- The CaMeL system has a fine-grained control for capabilities that I have not yet implemented in dromedary. This is in the roadmap.
- Integration with MCP for tool definitions.
- I want the Python interpreter to be performant and robust. This could be a challenge if it's written in Python. One idea is to use Rust to write the interpreter.
