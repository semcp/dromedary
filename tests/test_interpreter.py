#!/usr/bin/env python3

import os
import sys
import unittest
from interpreter import run_interpreter
from capability import CapabilityValue


class TestInterpreter(unittest.TestCase):
    """Test cases for the Python interpreter"""

    def get_value(self, result_value):
        if isinstance(result_value, CapabilityValue):
            return result_value.value
        return result_value

    def test_basic_operations(self):
        """Test basic arithmetic operations"""
        code = """
x = 5
y = 10
result = x + y
result
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), 15)

    def test_binary_arithmetic_operators(self):
        """Test all binary arithmetic operators"""
        code = """
a = 15
b = 4
results = [a + b, a - b, a * b, a / b, a // b, a % b, a ** 2]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        expected = [19, 11, 60, 3.75, 3, 3, 225]
        self.assertEqual(self.get_value(result["result"]), expected)

    def test_list_comprehensions_basic(self):
        """Test basic list comprehensions"""
        code = """
numbers = [1, 2, 3, 4, 5]
squares = [x * x for x in numbers]
squares
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [1, 4, 9, 16, 25])

    def test_list_comprehensions_with_conditions(self):
        """Test list comprehensions with if conditions"""
        code = """
numbers = list(range(10))
evens = [x for x in numbers if x % 2 == 0]
evens
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [0, 2, 4, 6, 8])

    def test_list_comprehensions_nested(self):
        """Test nested list comprehensions (flattening)"""
        code = """
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
flattened = [item for row in matrix for item in row]
flattened
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_list_comprehensions_variable_scoping(self):
        """Test that list comprehension variables don't leak to outer scope"""
        code = """
x = 100
numbers = [1, 2, 3]
result = [x + 1 for x in numbers]
final_x = x
[result, final_x]
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        expected_result, final_x = self.get_value(result["result"])
        self.assertEqual(expected_result, [2, 3, 4])
        self.assertEqual(final_x, 100)  # x should be unchanged

    def test_builtin_functions(self):
        """Test built-in functions"""
        code = """
numbers = [1, 2, 3, 4, 5]
results = [sum(numbers), max(numbers), min(numbers), len(numbers)]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [15, 5, 1, 5])

    def test_string_operations(self):
        """Test string operations and methods"""
        code = """
text = "Hello World"
results = [text.upper(), text.lower(), text.find("World"), text.count("l")]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), ["HELLO WORLD", "hello world", 6, 3])

    def test_dictionary_operations(self):
        """Test dictionary operations"""
        code = """
data = {'name': 'test', 'value': 42, 'active': True}
results = [list(data.keys()), list(data.values()), data.get('name'), data.get('missing', 'default')]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        keys, values, name, missing = self.get_value(result["result"])
        self.assertEqual(set(keys), {'name', 'value', 'active'})
        self.assertEqual(set(values), {'test', 42, True})
        self.assertEqual(name, 'test')
        self.assertEqual(missing, 'default')

    def test_slicing_operations(self):
        """Test list and string slicing"""
        code = """
data = list(range(10))
string = "Hello World"
results = [data[2:7], data[:5], data[5:], string[0:5]]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [[2, 3, 4, 5, 6], [0, 1, 2, 3, 4], [5, 6, 7, 8, 9], "Hello"])

    def test_control_flow_if_else(self):
        """Test if-elif-else control flow"""
        code = """
x = 5
if x > 10:
    result = "greater than 10"
elif x > 0:
    result = "positive"
else:
    result = "zero or negative"
result
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), "positive")

    def test_for_loops(self):
        """Test for loops"""
        code = """
total = 0
for i in range(5):
    total = total + i
total
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), 10)

    def test_tuple_unpacking(self):
        """Test tuple unpacking in assignments"""
        code = """
point = (3, 4)
x, y = point
[x, y]
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [3, 4])

    def test_starred_expressions(self):
        """Test starred expressions in lists"""
        code = """
list1 = [1, 2, 3]
list2 = [4, 5]
combined = [*list1, 0, *list2, 6]
combined
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), [1, 2, 3, 0, 4, 5, 6])

    def test_datetime_operations(self):
        """Test datetime operations"""
        code = """
current_date = date(2024, 6, 15)
tomorrow_date = current_date + timedelta(days=1)
tomorrow_date.isoformat()
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), "2024-06-16")

    def test_pydantic_models(self):
        """Test Pydantic model creation"""
        code = """
class TestModel(BaseModel):
    name: str
    email: EmailStr

test_obj = TestModel(name="Test User", email="test@example.com")
test_obj.name
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(self.get_value(result["result"]), "Test User")

    def test_tools_integration(self):
        """Test P-LLM tools integration"""
        code = """
current_day = get_current_day()
current_day
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertIsInstance(self.get_value(result["result"]), str)
        self.assertRegex(self.get_value(result["result"]), r'\d{4}-\d{2}-\d{2}')

    def test_syntax_errors(self):
        """Test that syntax errors are properly caught"""
        code = "print('unclosed string"
        result = run_interpreter(code)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "syntax")
        self.assertIsNotNone(result["error"])

    def test_runtime_errors(self):
        """Test that runtime errors are properly caught"""
        code = "print(undefined_variable)"
        result = run_interpreter(code)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "runtime")
        self.assertIsNotNone(result["error"])

    def test_error_recovery(self):
        """Test that interpreter can recover from errors"""
        # First run code with error
        error_code = "undefined_variable + 5"
        result1 = run_interpreter(error_code)
        self.assertFalse(result1["success"])
        
        # Then run valid code
        valid_code = "x = 5\ny = 10\nx + y"
        result2 = run_interpreter(valid_code)
        self.assertTrue(result2["success"])
        self.assertEqual(self.get_value(result2["result"]), 15)

    @unittest.skipUnless(os.getenv("AZURE_OPENAI_API_KEY"), "AZURE_OPENAI_API_KEY not set")
    def test_ai_assistant(self):
        """Test AI assistant integration"""
        code = """
class SimpleResponse(BaseModel):
    result: str

response = query_ai_assistant("What is the current year?", SimpleResponse)
response.result
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertIsInstance(self.get_value(result["result"]), str)

    def test_execution_trace_email_workflow(self):
        """Test execution trace for email retrieval and processing workflow (prompt1 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
received = get_received_emails()
last_email = received[-1]
body_text = last_email.body
today_iso = get_current_day()
today_date = datetime.fromisoformat(today_iso)
tomorrow_date = today_date + timedelta(days=1)
tomorrow_iso = tomorrow_date.isoformat()
tomorrow_iso
"""
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        trace = interpreter.get_execution_trace()
        
        expected_functions = ['get_received_emails', 'get_current_day']
        actual_functions = [call['function'] for call in trace]
        
        for expected_func in expected_functions:
            self.assertIn(expected_func, actual_functions)
        
        get_emails_call = next(call for call in trace if call['function'] == 'get_received_emails')
        self.assertEqual(get_emails_call['args'], [])
        self.assertEqual(get_emails_call['result_assigned_to'], 'received')
        
        get_day_call = next(call for call in trace if call['function'] == 'get_current_day')
        self.assertEqual(get_day_call['args'], [])
        self.assertEqual(get_day_call['result_assigned_to'], 'today_iso')

    def test_execution_trace_email_send_workflow(self):
        """Test execution trace for sending emails with variables (prompt1 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
bob_email = "bob.wilson@techcorp.com"
subject = "Meeting Reminder"
message_body = "Don't forget our meeting tomorrow"
result = send_email(
    recipients=[bob_email],
    subject=subject,
    body=message_body
)
result
"""
        result = interpreter.execute(code)
        if not result["success"]:
            print(f"Execution failed: {result['error']}")
            print(f"Error type: {result.get('error_type', 'unknown')}")
        self.assertTrue(result["success"], f"Execution failed: {result.get('error', 'Unknown error')}")
        
        trace = interpreter.get_execution_trace()
        self.assertEqual(len(trace), 1)
        
        send_call = trace[0]
        self.assertEqual(send_call['function'], 'send_email')
        self.assertEqual(send_call['result_assigned_to'], 'result')
        
        expected_kwargs = {'recipients', 'subject', 'body'}
        actual_kwargs = set(send_call['kwargs'].keys())
        self.assertEqual(actual_kwargs, expected_kwargs)
        
        self.assertEqual(send_call['kwargs']['subject'], 'subject')
        self.assertEqual(send_call['kwargs']['body'], 'message_body')

    def test_execution_trace_calendar_workflow(self):
        """Test execution trace for calendar operations (prompt3/4 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
today_str = get_current_day()
today_dt = datetime.strptime(today_str, "%Y-%m-%d")
yesterday_dt = today_dt - timedelta(days=1)
yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
events = get_day_calendar_events(yesterday_str)
events
"""
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        trace = interpreter.get_execution_trace()
        
        expected_functions = ['get_current_day', 'get_day_calendar_events']
        actual_functions = [call['function'] for call in trace]
        
        for expected_func in expected_functions:
            self.assertIn(expected_func, actual_functions)
        
        calendar_call = next(call for call in trace if call['function'] == 'get_day_calendar_events')
        self.assertEqual(calendar_call['args'], ['yesterday_str'])
        self.assertEqual(calendar_call['result_assigned_to'], 'events')

    def test_execution_trace_file_search_workflow(self):
        """Test execution trace for file search operations (prompt5 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
files_by_name = search_files_by_filename("meeting notes")
if not files_by_name:
    files_by_content = search_files("meeting notes")
files_by_name
"""
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        trace = interpreter.get_execution_trace()
        
        search_calls = [call for call in trace if 'search_files' in call['function']]
        self.assertGreaterEqual(len(search_calls), 1)
        
        filename_search = next(call for call in trace if call['function'] == 'search_files_by_filename')
        self.assertEqual(filename_search['result_assigned_to'], 'files_by_name')

    def test_execution_trace_ai_assistant_with_schema(self):
        """Test execution trace for AI assistant calls with custom schemas (prompt2/5 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
class BobEmail(BaseModel):
    email: EmailStr

text_content = "Contact Bob at bob@example.com for more details"
parsed = query_ai_assistant(
    f"Extract Bob's email address from: {text_content}",
    output_schema=BobEmail
)
bob_email = parsed.email
bob_email
"""
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        trace = interpreter.get_execution_trace()
        
        ai_calls = [call for call in trace if call['function'] == 'query_ai_assistant']
        self.assertEqual(len(ai_calls), 1)
        
        ai_call = ai_calls[0]
        self.assertEqual(ai_call['result_assigned_to'], 'parsed')
        self.assertIn('output_schema', ai_call['kwargs'])

    def test_execution_trace_complex_workflow_with_list_comprehension(self):
        """Test execution trace for complex workflow with list operations (prompt3 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
events = get_day_calendar_events("2024-01-01")
participants_list = [
    participant
    for event in events
    for participant in event.get("participants", [])
]
participants = sorted(set(participants_list))
result = send_email(
    recipients=participants,
    subject="Follow-up",
    body="Thank you for attending"
)
result
"""
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        trace = interpreter.get_execution_trace()
        
        expected_functions = ['get_day_calendar_events', 'sorted', 'set', 'send_email']
        actual_functions = [call['function'] for call in trace]
        
        for expected_func in expected_functions:
            self.assertIn(expected_func, actual_functions)
        
        send_call = next(call for call in trace if call['function'] == 'send_email')
        self.assertEqual(send_call['kwargs']['recipients'], 'participants')

    def test_execution_trace_email_processing_chain(self):
        """Test execution trace for email processing chain (prompt2 style)"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        code = """
emails = get_unread_emails()
if emails:
    text_pieces = [
        "Email " + str(idx) + ": " + email.subject
        for idx, email in enumerate(emails, start=1)
    ]
    emails_text = "".join(text_pieces)
    
    class SummaryOutput(BaseModel):
        summary: str
    
    result = query_ai_assistant(emails_text, output_schema=SummaryOutput)
    summary = result.summary
else:
    summary = "No emails"
summary
"""
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        trace = interpreter.get_execution_trace()
        
        unread_call = next((call for call in trace if call['function'] == 'get_unread_emails'), None)
        self.assertIsNotNone(unread_call)
        self.assertEqual(unread_call['result_assigned_to'], 'emails')

    def test_execution_trace_clear_between_workflows(self):
        """Test that execution trace properly clears between different workflows"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        
        code1 = """
emails = get_received_emails()
last_email = emails[-1]
last_email
"""
        result1 = interpreter.execute(code1)
        self.assertTrue(result1["success"])
        
        trace1 = interpreter.get_execution_trace()
        initial_trace_length = len(trace1)
        self.assertGreater(initial_trace_length, 0)
        
        interpreter.clear_execution_trace()
        
        code2 = """
today = get_current_day()
events = get_day_calendar_events(today)
events
"""
        result2 = interpreter.execute(code2)
        self.assertTrue(result2["success"])
        
        trace2 = interpreter.get_execution_trace()
        
        trace2_functions = [call['function'] for call in trace2]
        self.assertIn('get_current_day', trace2_functions)
        self.assertIn('get_day_calendar_events', trace2_functions)
        self.assertNotIn('get_received_emails', trace2_functions)

    def test_multi_conversation_state_isolation(self):
        """Test that multiple conversations are properly isolated with no residual state"""
        from visualizer import InterpreterVisualized
        from interpreter import PythonInterpreter
        
        viz_interpreter = InterpreterVisualized(PythonInterpreter)
        
        code1 = """
bob_email = "bob.wilson@techcorp.com"
subject = "Meeting Reminder"
message_body = "Don't forget our meeting tomorrow"
result1 = send_email(recipients=[bob_email], subject=subject, body=message_body)
result1
"""
        
        result1 = viz_interpreter.execute(code1)
        if not result1["success"]:
            print(f"Conversation 1 execution failed: {result1['error']}")
            print(f"Error type: {result1.get('error_type', 'unknown')}")
        self.assertTrue(result1["success"], f"Conversation 1 failed: {result1.get('error', 'Unknown error')}")
        
        self.assertIn('bob_email', viz_interpreter.interpreter.globals)
        self.assertIn('subject', viz_interpreter.interpreter.globals)
        self.assertIn('message_body', viz_interpreter.interpreter.globals)
        self.assertIn('result1', viz_interpreter.interpreter.globals)
        
        trace1 = viz_interpreter.interpreter.get_execution_trace()
        self.assertGreater(len(trace1), 0)
        self.assertEqual(trace1[0]['function'], 'send_email')

        viz_interpreter.clear_for_new_conv()
        
        self.assertNotIn('bob_email', viz_interpreter.interpreter.globals)
        self.assertNotIn('subject', viz_interpreter.interpreter.globals)
        self.assertNotIn('message_body', viz_interpreter.interpreter.globals)
        self.assertNotIn('result1', viz_interpreter.interpreter.globals)
        
        trace_after_clear = viz_interpreter.interpreter.get_execution_trace()
        self.assertEqual(len(trace_after_clear), 0)
        
        self.assertIn('send_email', viz_interpreter.interpreter.globals)
        self.assertIn('get_current_day', viz_interpreter.interpreter.globals)
        self.assertIn('print', viz_interpreter.interpreter.globals)
        self.assertIn('str', viz_interpreter.interpreter.globals)
        
        code2 = """
alice_email = "alice.cooper@clientcorp.com"
event_title = "Team Standup"
current_day = get_current_day()
calendar_events = get_day_calendar_events(current_day)
result2 = len(calendar_events)
result2
"""
        
        result2 = viz_interpreter.execute(code2)
        self.assertTrue(result2["success"])
        
        self.assertIn('alice_email', viz_interpreter.interpreter.globals)
        self.assertIn('event_title', viz_interpreter.interpreter.globals)
        self.assertIn('current_day', viz_interpreter.interpreter.globals)
        self.assertIn('result2', viz_interpreter.interpreter.globals)
        
        self.assertNotIn('bob_email', viz_interpreter.interpreter.globals)
        self.assertNotIn('subject', viz_interpreter.interpreter.globals)
        self.assertNotIn('message_body', viz_interpreter.interpreter.globals)
        self.assertNotIn('result1', viz_interpreter.interpreter.globals)
        
        trace2 = viz_interpreter.interpreter.get_execution_trace()
        trace2_functions = [call['function'] for call in trace2]
        
        self.assertIn('get_current_day', trace2_functions)
        self.assertIn('get_day_calendar_events', trace2_functions)
        self.assertIn('len', trace2_functions)
        self.assertNotIn('send_email', trace2_functions)

    def test_interpreter_globals_reset(self):
        """Test that interpreter globals properly reset to initial state"""
        from interpreter import PythonInterpreter
        
        interpreter = PythonInterpreter()
        
        initial_globals = set(interpreter.globals.keys())
        
        code = """
user_data = "sensitive info"
computed_value = 42 * 2
temp_list = [1, 2, 3, 4, 5]
temp_dict = {"key": "value"}
user_data
"""
        
        result = interpreter.execute(code)
        self.assertTrue(result["success"])
        
        self.assertIn('user_data', interpreter.globals)
        self.assertIn('computed_value', interpreter.globals)
        self.assertIn('temp_list', interpreter.globals)
        self.assertIn('temp_dict', interpreter.globals)
        
        post_execution_globals = set(interpreter.globals.keys())
        new_variables = post_execution_globals - initial_globals
        self.assertEqual(new_variables, {'user_data', 'computed_value', 'temp_list', 'temp_dict'})
        
        interpreter.reset_globals()
        
        post_reset_globals = set(interpreter.globals.keys())
        self.assertEqual(post_reset_globals, initial_globals)
        
        self.assertNotIn('user_data', interpreter.globals)
        self.assertNotIn('computed_value', interpreter.globals)
        self.assertNotIn('temp_list', interpreter.globals)
        self.assertNotIn('temp_dict', interpreter.globals)
        
        self.assertIn('print', interpreter.globals)
        self.assertIn('len', interpreter.globals)
        self.assertIn('str', interpreter.globals)
        self.assertIn('send_email', interpreter.globals)

    def test_dependency_graph_isolation_between_conversations(self):
        """Test that dependency graphs don't contaminate between conversations"""
        from visualizer import InterpreterVisualized
        from interpreter import PythonInterpreter
        
        viz_interpreter = InterpreterVisualized(PythonInterpreter)
        
        code1 = """
emails = get_received_emails()
first_email = emails[0] if emails else None
first_email
"""
        
        result1 = viz_interpreter.execute(code1)
        self.assertTrue(result1["success"])
        
        graph1_nodes = set(viz_interpreter.visualizer.graph.nodes())
        self.assertGreater(len(graph1_nodes), 0)
        
        expected_var_nodes1 = {'var_emails', 'var_first_email'}
        actual_var_nodes1 = {node for node in graph1_nodes if node.startswith('var_')}
        self.assertTrue(expected_var_nodes1.issubset(actual_var_nodes1))
        
        viz_interpreter.clear_for_new_conv()
        
        graph_after_clear = set(viz_interpreter.visualizer.graph.nodes())
        self.assertEqual(len(graph_after_clear), 0)
        
        code2 = """
current_time = get_current_day()
file_list = list_files()
file_count = len(file_list)
file_count
"""
        
        result2 = viz_interpreter.execute(code2)
        self.assertTrue(result2["success"])
        
        graph2_nodes = set(viz_interpreter.visualizer.graph.nodes())
        
        expected_var_nodes2 = {'var_current_time', 'var_file_list', 'var_file_count'}
        actual_var_nodes2 = {node for node in graph2_nodes if node.startswith('var_')}
        self.assertTrue(expected_var_nodes2.issubset(actual_var_nodes2))
        
        contamination_nodes = {'var_emails', 'var_first_email'}
        actual_contamination = contamination_nodes.intersection(graph2_nodes)
        self.assertEqual(len(actual_contamination), 0, f"Found contamination: {actual_contamination}")

    def test_retry_state_cleanup_simulation(self):
        """Test that retry cleanup properly handles failed executions"""
        from visualizer import InterpreterVisualized
        from interpreter import PythonInterpreter
        
        viz_interpreter = InterpreterVisualized(PythonInterpreter)
        
        code_partial = """
emails = get_received_emails()
sender = emails[0].sender if emails else "unknown"
# This would continue but let's say it fails here
"""
        
        result1 = viz_interpreter.execute(code_partial)
        self.assertTrue(result1["success"])
        
        self.assertIn('emails', viz_interpreter.interpreter.globals)
        self.assertIn('sender', viz_interpreter.interpreter.globals)
        
        trace1 = viz_interpreter.interpreter.get_execution_trace()
        self.assertGreater(len(trace1), 0)
        
        viz_interpreter.clear_for_new_conv()
        
        self.assertNotIn('emails', viz_interpreter.interpreter.globals)
        self.assertNotIn('sender', viz_interpreter.interpreter.globals)
        
        trace_after_cleanup = viz_interpreter.interpreter.get_execution_trace()
        self.assertEqual(len(trace_after_cleanup), 0)
        
        graph_after_cleanup = set(viz_interpreter.visualizer.graph.nodes())
        self.assertEqual(len(graph_after_cleanup), 0)
        code_retry = """
current_day = get_current_day()
file_info = list_files()
status = "retry successful"
status
"""
        
        result_retry = viz_interpreter.execute(code_retry)
        self.assertTrue(result_retry["success"])
        
        self.assertIn('current_day', viz_interpreter.interpreter.globals)
        self.assertIn('file_info', viz_interpreter.interpreter.globals)
        self.assertIn('status', viz_interpreter.interpreter.globals)
        self.assertNotIn('emails', viz_interpreter.interpreter.globals)
        self.assertNotIn('sender', viz_interpreter.interpreter.globals)


if __name__ == "__main__":
    unittest.main() 