"""
P-LLM Test Suite

This directory contains all test files for the P-LLM system:
- test_interpreter.py: Tests for the Python interpreter
- test_policies.py: Tests for the policy engine
- test_tools.py: Tests for the tool system
"""

import os
import sys

# Add the parent directory to the Python path so test files can import P-LLM modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 