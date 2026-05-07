# Testing Guide

This document provides guidelines for writing and running tests in NanoAgent.

## Running Tests

### Run all tests
```bash
pytest tests/ -v
```

### Run with coverage
```bash
pytest tests/ --cov=nano_agent --cov-report=term-missing
```

### Run specific test categories
```bash
# Unit tests only
pytest tests/ -m unit

# Integration tests only
pytest tests/ -m integration

# Skip slow tests
pytest tests/ -m "not slow"
```

### Run specific test file
```bash
pytest tests/test_memory.py -v
```

### Run specific test class
```bash
pytest tests/test_memory.py::TestShortTermMemory -v
```

### Run specific test method
```bash
pytest tests/test_memory.py::TestShortTermMemory::test_add_user_message -v
```

---

## Test Markers

NanoAgent uses pytest markers to categorize tests:

| Marker | Description | Usage |
|--------|-------------|-------|
| `@pytest.mark.unit` | Unit tests - fast, isolated, no external dependencies | Default for most tests |
| `@pytest.mark.integration` | Integration tests - require real dependencies | For end-to-end tests |
| `@pytest.mark.slow` | Slow running tests | For tests that take >1s |

### Adding markers

**File-level marker (recommended):**
```python
import pytest

pytestmark = pytest.mark.unit

class TestMyClass:
    def test_something(self):
        ...
```

**Class-level marker:**
```python
import pytest

@pytest.mark.integration
class TestMyIntegration:
    def test_something(self):
        ...
```

**Method-level marker:**
```python
import pytest

class TestMyClass:
    @pytest.mark.slow
    def test_slow_operation(self):
        ...
```

---

## Using Fixtures

NanoAgent provides shared fixtures in `tests/conftest.py`.

### Directory and Storage Fixtures

```python
def test_with_temp_dir(temp_dir):
    """temp_dir is a Path object pointing to a temporary directory."""
    file_path = temp_dir / "test.txt"
    file_path.write_text("test")
    assert file_path.exists()

def test_with_storage(temp_storage):
    """temp_storage is a FileStorage instance."""
    entry = MemoryEntry.create(session_id="test", role="user", content="hi")
    temp_storage.save(entry)
    assert temp_storage.session_exists("test")

def test_with_sqlite(temp_sqlite_storage):
    """temp_sqlite_storage is a SQLiteStorage instance."""
    ...
```

### Memory Fixtures

```python
def test_short_term(short_term_memory):
    """short_term_memory is a ShortTermMemory instance."""
    short_term_memory.add_user_message("Hello")
    assert len(short_term_memory) == 2

def test_persistent(persistent_memory):
    """persistent_memory is a PersistentMemory instance."""
    persistent_memory.add_user_message("Test")
    assert len(persistent_memory) == 2

def test_hybrid(hybrid_memory):
    """hybrid_memory is a HybridMemory instance."""
    hybrid_memory.memorize("User likes Python", category="preference")
    results = hybrid_memory.recall("Python")
    assert len(results) == 1
```

### Mock Fixtures

```python
def test_with_mock_llm(mock_llm):
    """mock_llm is a Mock object configured for LLM interface."""
    mock_llm.chat.return_value = ("Response", [], LLMUsage())
    
    agent = ReActAgent(llm=mock_llm, ...)
    result = agent.run("test")
    assert mock_llm.chat.called

def test_with_mock_tool(mock_tool):
    """mock_tool is a mock tool instance."""
    registry = ToolRegistry()
    registry.register(mock_tool)
    ...
```

---

## Test Data Factories

Use factories from `tests/factories.py` for consistent test data creation.

### Message Factories

```python
from tests.factories import create_message, create_user_message

def test_messages():
    msg = create_message(role="user", content="Hello")
    assert msg["role"] == "user"
    
    user_msg = create_user_message("Hi")
    assert user_msg["content"] == "Hi"
```

### Memory Entry Factories

```python
from tests.factories import create_memory_entry, create_long_term_entry

def test_entries():
    entry = create_memory_entry(session_id="test", content="Hello")
    assert entry.session_id == "test"
    
    ltm = create_long_term_entry(content="User likes Python", category="preference")
    assert ltm.category == "preference"
```

### Config Factories

```python
from tests.factories import create_config, create_llm_config

def test_config():
    config = create_config(llm=create_llm_config(model="test-model"))
    assert config.llm.model == "test-model"
```

### Tool Factories

```python
from tests.factories import create_mock_tool, create_tool_registry_with_tools

def test_tools():
    tool = create_mock_tool(name="test_tool", output="result")
    result = tool.execute(input="test")
    assert result.success
    
    registry = create_tool_registry_with_tools("tool1", "tool2")
    assert len(registry) == 2
```

---

## Test Naming Conventions

Follow these naming conventions for consistency:

### Test file names
- Pattern: `test_<module>.py`
- Example: `test_memory.py`, `test_agent.py`

### Test class names
- Pattern: `Test<ClassName>` or `Test<Feature>`
- Example: `TestShortTermMemory`, `TestSessionCleanup`

### Test method names
- Pattern: `test_<method>_<scenario>_<expected_result>`
- Example: `test_add_user_message_with_valid_content_succeeds`

### Docstrings
Always add docstrings to test methods:
```python
def test_add_user_message(self):
    """Test adding user message to memory."""
    ...
```

---

## Best Practices

### 1. Use Arrange-Act-Assert pattern
```python
def test_memory_add():
    # Arrange
    memory = ShortTermMemory()
    message = {"role": "user", "content": "test"}

    # Act
    memory.add(message)

    # Assert
    assert len(memory) == 2
```

### 2. Use parametrized tests for similar cases
```python
@pytest.mark.parametrize("role,expected", [
    ("user", "user"),
    ("assistant", "assistant"),
    ("system", "system"),
])
def test_message_roles(role, expected):
    msg = create_message(role=role)
    assert msg["role"] == expected
```

### 3. Mock external dependencies
```python
def test_with_mocked_http():
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"data": "test"}
        # Test code that makes HTTP requests
```

### 4. Use fixtures for test isolation
```python
def test_isolated_storage(temp_storage):
    # Each test gets a fresh storage instance
    # No need to clean up manually
    ...
```

### 5. Test edge cases
```python
def test_empty_input():
    """Test handling of empty input."""
    result = tool.execute(input="")
    assert result.success

def test_none_input():
    """Test handling of None input."""
    with pytest.raises(ValueError):
        tool.execute(input=None)
```

---

## Test Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| Core (agent, memory) | 80% |
| Tools | 75% |
| CLI | 70% |
| Overall | 75% |

Check coverage with:
```bash
pytest tests/ --cov=nano_agent --cov-report=html
open htmlcov/index.html
```
