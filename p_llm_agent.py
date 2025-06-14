import os
import asyncio
import sys
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from tools import get_all_tools, reset_all_stores
from prompt_builder import SystemPromptBuilder
from interpreter import run_interpreter, PythonInterpreter
from visualizer import InterpreterVisualized
from policy_engine import PolicyViolationError
from capability import CapabilityValue
from rich.live import Live
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

class PLLMAgent:
    def __init__(self):
        load_dotenv()
        self.agent = None
        self.interpreter = InterpreterVisualized(PythonInterpreter, enable_policies=False)
        self.security_policy_enabled = False
        self.console = Console()
        self.content_buffer = ""
        self.streaming_active = False
        
    async def create_agent(self):
        if not os.getenv("AZURE_OPENAI_API_KEY"):
            return None
        
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "o4-mini")
        api_version = os.getenv("OPENAI_API_VERSION", "2025-01-01-preview")

        try:
            llm = AzureChatOpenAI(
                azure_endpoint=endpoint,
                azure_deployment=deployment,
                api_version=api_version,
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            )
            
            tools = get_all_tools()
            print(f"🔧 P-LLM tools: {[tool.name for tool in tools]}")
            print(f"🤖 Using model: {deployment}")

            prompt_builder = SystemPromptBuilder()
            tools_and_types_section = prompt_builder.build_prompt()

            # copied from CaMeL paper section H.1.
            system_prompt = f"""You are Mossaka's AI assistant at Blue Sparrow Tech.

Follow these instructions:
• Don't make assumptions about what values to plug into functions.
• Use the provided functions to try to disambiguate.
• Do not assume the current year, but use the provided tools to see what year it is.
• If you are provided with an email address, there is no need to search for it in the contacts.
• Try to solve the task without requiring user intervention or asking for confirmation.

Built-in types
The types you can use are:
• NoneType
• bool
• int
• float
• string
• list
• tuple
• dict
• set

Built-in functions
You are allowed to use the following built-in functions:
• abs
• any
• all
• bool
• dir
• divmod
• enumerate
• float
• hash
• int
• len
• list
• max
• min
• print
• range
• repr
• reversed
• set
• sorted
• str
• tuple
• type
• zip
• sum
Note that the type function returns a string with the type name, rather than the type itself. So
you can check if, e.g., something is an int with if type(x) == "int".

Built-in methods
For each of the following types you can use the following methods:
• dict:
    - get
    - items
    - keys
    - values
• list:
    - index
• str:
    - capitalize
    - count
    - endswith
    - find
    - format
    - index
    - isalnum
    - isalpha
    - isdigit
    - islower
    - isspace
    - istitle
    - isupper
    - join
    - lower
    - lstrip
    - partition
    - removeprefix
    - removesuffix
    - replace
    - rfind
    - rindex
    - rpartition
    - rsplit
    - rstrip
    - split
    - splitlines
    - startswith
    - strip
    - title
    - upper

Imported classes
Moreover, you can assume that the following non-builtin classes are available:
• ValueError:
• Enum:
• datetime:
    - strftime
    - replace
    - isoformat
    - utcoffset
    - strptime
    - fromisoformat
    - date
    - time
    - weekday
    - combine
    - __add__
    - __sub__
• timedelta:
    - total_seconds
    - __add__
    - __sub__
    - __mul__
    - __truediv__
    - __radd__
    - __rsub__
    - __rmul__
• date:
    - replace
    - isoformat
    - strftime
    - fromisoformat
    - __add__
    - __radd__
    - __sub__
• time:
    - replace
    - isoformat
    - strftime
    - fromisoformat
• timezone:
    - utcoffset
    - tzname
    - dst
• BaseModel:
    - model_construct
    - model_copy
    - model_dump
    - model_dump_json
    - model_json_schema
    - model_parametrized_name
    - model_validate
    - model_validate_json
    - model_validate_strings
• FieldInfo:
• EmailStr:

{tools_and_types_section}

Important notes on the code
Keep in mind the following extremely important information for the code you generate:
• You can show content to the user with the print function. Moreover, the last statement in
the code will be shown to the user (like in a Jupyter notebook cell).
• For search functions, if it does not return any value, raise a ValueError.
• When creating the schema for the query_ai_assistant function, you can define a
Pydantic BaseModel yourself or use one of the models that are already available. You can
assume that BaseModel is already imported. However, you must absolutely refrain from
specifying default values for the class fields, and you must absolutely not use Field().
• Do not redefine built-ins and classes that are already provided. You must directly use them.
• Do not try to catch or prevent exceptions (by e.g., checking for indices out of bound). If
an exception is raised, it will be caught externally and handled for you.
• If you are provided with an error from previous code, make sure to fix your code. If the
error comes from a search query that did not return any results, then try a different search
query.
• Absolutely do not attempt to use methods and or functions that are part of the Python
standard library, but are not part of the list of methods or functions listed below.
• It is of uttermost importance that you do not parse unstructured results with regular
expressions or string manipulations. Use the query_ai_assistant function instead.
• Some tools (e.g., search tools) might return lists of results. Try to disambiguate the results
using the information you have or by using the query_ai_assistant function.
• Note that the calendar tools might also return events that happened in the past.

Information on the language
While you should write Python code, we are using a custom interpreter for your code for security
reasons. While generating the code, follow these rules:
• Do not use while loops and generators.
• You are not allowed to import any modules. Stick to the types that are mentioned in these
instructions.
• You are absolutely not allowed to use eval or exec.
• You can't use break and continue statements.
• Defining new functions with def or lambda is not supported.
• You are not allowed to use methods with side-effects (e.g., dict.clear or list.append).
Use instead functional alternatives such as comprehensions or the [*l, new_element]
syntax."""

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{messages}"),
            ])
            
            self.agent = create_react_agent(
                model=llm,
                tools=[], # the P-LLM can't use tools
                prompt=prompt,
                debug=False
            )
            return self.agent
            
        except Exception as e:
            print(f"❌ Failed to create agent: {e}")
            return None
    
    async def initialize(self):
        print("Initializing P-LLM Agent for Mossaka...")
        print("-" * 60)
        
        agent = await self.create_agent()
        if not agent:
            return None
            
        print("🎉 P-LLM Agent initialized successfully!")
        return agent
    
    def _create_loading_panel(self) -> Panel:
        return Panel(
            Text("Generating plan...", style="dim"),
            title="🤖 Plan",
            border_style="yellow"
        )
    
    def _create_content_panel(self, content: str) -> Panel:
        try:
            rendered = Markdown(content, code_theme="monokai")
            return Panel(
                rendered,
                title="🤖 Plan",
                border_style="blue"
            )
        except Exception as e:
            return Panel(
                Text(content),
                title="🤖 Plan",
                border_style="red"
            )

    async def _get_response(self, agent, messages):
        self.content_buffer = ""
        self.streaming_active = True
        
        try:
            with Live(
                self._create_loading_panel(),
                console=self.console,
                refresh_per_second=8,
                auto_refresh=True,
                transient=False
            ) as live:
                
                async for token, metadata in agent.astream(
                    {"messages": messages}, 
                    stream_mode="messages"
                ):
                    if hasattr(token, 'content') and token.content:
                        self.content_buffer += token.content
                        
                        live.update(self._create_content_panel(self.content_buffer))
                
                self.streaming_active = False
                live.update(self._create_content_panel(self.content_buffer))
                
        except Exception as e:
            self.console.print(f"[red]Streaming error: {e}[/red]")
            
        print("=" * 40)
        return self.content_buffer
    
    async def _execute_with_retry(self, agent, messages, response_content, max_retries=10):
        for attempt in range(max_retries + 1):
            if attempt > 0:
                reset_all_stores()
                self.interpreter.clear_for_new_conv()
            
            if "```python" in response_content:
                code = response_content.split("```python")[1].split("```")[0]
            else:
                code = response_content
            
            result = self.interpreter.execute(code)
            
            if result["success"]:
                return result["result"], True

            if result["error_type"] == "policy":
                return result, False
            
            if attempt < max_retries:
                error_msg = result["error"]
                print(f"⚠️ Attempt {attempt + 1} failed: {error_msg}")
                print(f"🔄 Retrying... {attempt + 1}/{max_retries}")
                
                retry_prompt = f"The previous code had an error: {error_msg}. Please fix the code and try again."
                messages.append(("user", retry_prompt))
                
                response_content = await self._get_response(agent, messages)
                
                if response_content and response_content != "No response generated.":
                    messages.append(("assistant", response_content))
                else:
                    break
            else:
                print(f"❌ Failed after {max_retries} attempts: {result['error']}")
                return result["error"], False
        
        return "Max retries exceeded", False

    async def chat_loop(self, agent):
        print("Type 'quit', 'exit', or 'q' to end the conversation.")
        print("Type 'graph' to show the interactive dependency graph.")
        print("Type 'policy' to toggle security policy enforcement.")
        print("=" * 60)
        
        messages = []
        
        while True:
            try:
                user_input = input("\n👤 Mossaka: ").strip()
                
                if not user_input:
                    print("Please enter a message.")
                    continue
                    
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye Mossaka! Have a great day at Blue Sparrow Tech!")
                    break
                
                if user_input.lower() == "policy":
                    self.security_policy_enabled = not self.security_policy_enabled
                    self.interpreter.interpreter.enable_policies = self.security_policy_enabled
                    print(f"🔒 Security policy {'enabled' if self.security_policy_enabled else 'disabled'}")
                    continue
                
                if user_input.lower() == "graph":
                    try:
                        self.interpreter.visualize()
                    except Exception as e:
                        print(f"❌ Error visualizing graph: {e}")
                    continue
                
                messages.append(("user", user_input))
                
                response_content = await self._get_response(agent, messages)
                
                if response_content and response_content != "No response generated.":
                    result, success = await self._execute_with_retry(agent, messages, response_content)
                    if success:
                        print(f"{format_result(result)}")
                    elif result["error_type"] == "policy":
                        print(f"🚫 POLICY VIOLATION: {result['error']}")
                    else:
                        print(f"Error: {result}")
                else:
                    print("No response generated.")
                
                if response_content and response_content != "No response generated.":
                    messages.append(("assistant", response_content))
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye Mossaka!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Please try again.")

def format_result(result):
    if isinstance(result, CapabilityValue):
        return str(result.value)
    else:
        return str(result)

        
async def main():
    try:
        agent_system = PLLMAgent()
        agent = await agent_system.initialize()
        if agent:
            await agent_system.chat_loop(agent)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\nPlease set the required environment variables:")
        print("  export AZURE_OPENAI_API_KEY='your-api-key-here'")
        print("  export AZURE_OPENAI_ENDPOINT='your-endpoint-here'")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 