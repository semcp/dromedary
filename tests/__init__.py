"""
P-LLM Test Suite

This directory contains all test files for the P-LLM system:
- test_integration.py: Integration tests for the P-LLM system
- mcp/: Tests for MCP components
- testdata/: Test data files
"""

import os
import sys

# Add the parent directory to the Python path so test files can import P-LLM modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 