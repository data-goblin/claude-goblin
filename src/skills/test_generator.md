# Test Generator

Generate comprehensive unit tests for Python code following best practices.

## When to Use

Activate this skill when:
- User asks to "write tests for..."
- User asks to "add test coverage for..."
- User asks to "create unit tests..."
- User wants to test a specific function or class

## Instructions

When generating tests:

1. **Analyze the target code**
   - Identify all public functions and methods
   - Note input parameters and return types
   - Find edge cases and boundary conditions
   - Check for error handling paths

2. **Structure tests properly**
   - Use pytest as the testing framework
   - Group tests by function/class in test classes
   - Use descriptive test names: `test_<function>_<scenario>_<expected>`
   - Add docstrings explaining what each test verifies

3. **Cover these scenarios**
   - Happy path (normal operation)
   - Edge cases (empty inputs, None, boundary values)
   - Error cases (invalid inputs, exceptions)
   - Type variations (if applicable)

4. **Use fixtures effectively**
   - Create fixtures for common setup
   - Use `@pytest.fixture` decorator
   - Prefer function-scoped fixtures unless sharing is needed

5. **Mock external dependencies**
   - Use `unittest.mock.patch` for external calls
   - Mock file I/O, network requests, databases
   - Verify mock calls with `assert_called_*` methods

## Example Output

```python
import pytest
from unittest.mock import Mock, patch

from mymodule import calculate_total


class TestCalculateTotal:
    """Tests for the calculate_total function."""

    def test_calculate_total_with_valid_items_returns_sum(self):
        """Verify total calculation with normal input."""
        items = [{"price": 10.00}, {"price": 20.00}]
        result = calculate_total(items)
        assert result == 30.00

    def test_calculate_total_with_empty_list_returns_zero(self):
        """Verify empty list returns zero."""
        assert calculate_total([]) == 0.0

    def test_calculate_total_with_none_raises_type_error(self):
        """Verify None input raises appropriate error."""
        with pytest.raises(TypeError):
            calculate_total(None)

    @pytest.fixture
    def sample_items(self):
        """Provide sample items for testing."""
        return [
            {"price": 10.00, "quantity": 2},
            {"price": 5.00, "quantity": 1},
        ]
```

## Best Practices

- Aim for high coverage but prioritize meaningful tests
- Test behavior, not implementation details
- Keep tests independent and idempotent
- Use parametrize for testing multiple inputs
- Include both positive and negative test cases
