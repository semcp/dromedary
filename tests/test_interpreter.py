#!/usr/bin/env python3

import os
import sys
import unittest
from interpreter import run_interpreter


class TestInterpreter(unittest.TestCase):
    """Test cases for the Python interpreter"""

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
        self.assertEqual(result["result"], 15)

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
        self.assertEqual(result["result"], expected)

    def test_list_comprehensions_basic(self):
        """Test basic list comprehensions"""
        code = """
numbers = [1, 2, 3, 4, 5]
squares = [x * x for x in numbers]
squares
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], [1, 4, 9, 16, 25])

    def test_list_comprehensions_with_conditions(self):
        """Test list comprehensions with if conditions"""
        code = """
numbers = list(range(10))
evens = [x for x in numbers if x % 2 == 0]
evens
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], [0, 2, 4, 6, 8])

    def test_list_comprehensions_nested(self):
        """Test nested list comprehensions (flattening)"""
        code = """
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
flattened = [item for row in matrix for item in row]
flattened
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], [1, 2, 3, 4, 5, 6, 7, 8, 9])

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
        expected_result, final_x = result["result"]
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
        self.assertEqual(result["result"], [15, 5, 1, 5])

    def test_string_operations(self):
        """Test string operations and methods"""
        code = """
text = "Hello World"
results = [text.upper(), text.lower(), text.find("World"), text.count("l")]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], ["HELLO WORLD", "hello world", 6, 3])

    def test_dictionary_operations(self):
        """Test dictionary operations"""
        code = """
data = {'name': 'test', 'value': 42, 'active': True}
results = [list(data.keys()), list(data.values()), data.get('name'), data.get('missing', 'default')]
results
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        keys, values, name, missing = result["result"]
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
        self.assertEqual(result["result"], [[2, 3, 4, 5, 6], [0, 1, 2, 3, 4], [5, 6, 7, 8, 9], "Hello"])

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
        self.assertEqual(result["result"], "positive")

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
        self.assertEqual(result["result"], 10)

    def test_tuple_unpacking(self):
        """Test tuple unpacking in assignments"""
        code = """
point = (3, 4)
x, y = point
[x, y]
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], [3, 4])

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
        self.assertEqual(result["result"], [1, 2, 3, 0, 4, 5, 6])

    def test_datetime_operations(self):
        """Test datetime operations"""
        code = """
current_date = date(2024, 6, 15)
tomorrow_date = current_date + timedelta(days=1)
tomorrow_date.isoformat()
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], "2024-06-16")

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
        self.assertEqual(result["result"], "Test User")

    def test_tools_integration(self):
        """Test P-LLM tools integration"""
        code = """
current_day = get_current_day()
current_day
"""
        result = run_interpreter(code)
        self.assertTrue(result["success"])
        self.assertIsInstance(result["result"], str)
        self.assertRegex(result["result"], r'\d{4}-\d{2}-\d{2}')

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
        self.assertEqual(result2["result"], 15)

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
        self.assertIsInstance(result["result"], str)


if __name__ == "__main__":
    unittest.main() 