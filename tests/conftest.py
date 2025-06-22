import sys
import os
from pathlib import Path
import pytest

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

@pytest.fixture(scope="session")
def project_root_path():
    return project_root

@pytest.fixture(autouse=True)
def setup_test_environment():
    os.environ['MCP_TESTING'] = 'true'
    yield
    if 'MCP_TESTING' in os.environ:
        del os.environ['MCP_TESTING'] 