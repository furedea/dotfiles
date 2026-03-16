---
name: python
description: >
  Python coding style and project conventions: uv package management, pytest/anyio testing,
  pyright type checking, src/ layout, dataclass Value Objects, __slots__, structured dict
  logging, naming conventions, whitespace rules, and docstring formats.
  Load this skill whenever writing, reviewing, or refactoring any Python code — including
  when creating new files, adding tests, fixing bugs, designing classes, or setting up a project.
  Trigger on .py files, pytest, uv, pyright, dataclass, pydantic, or any Python-related task.
---

# Python Coding Style Guidelines

## Package Management

- Use only `uv` for package management, don't use `pip`
- Initialize a new project using `uv init {project-name}`
- Install dependencies using `uv sync`
- Install packages using `uv add {package}`
- Run tools using `uv run {tool}`
- Upgrade packages using `uv add --dev {package} --upgrade-package {package}`
- Prohibited: `uv pip install`, `@latest`

## Directory Structure

- Store production code including entry points in `./src` directory
- Store test code in `./tests` directory

## File Standards

- Keep code within 119 characters per line (URLs may exceed this limit)
- Always include type hints
- Use pyright for static analysis

## Testing

- Use only `pytest` as test framework, do not use `unittest`
- Run tests using `uv run --frozen pytest`
- Use `anyio` for async tests, do not use `asyncio`
- Use `pytest` and `anyio` with `--dev` flag as they are development packages
- Test coverage should include edge cases and errors
- Always add tests for new features
- Add unit tests for bug fixes

Async test pattern:

```python
# conftest.py
import pytest

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

# tests/test_xxx.py
import pytest

@pytest.mark.anyio
async def test_something() -> None:
    result = await some_async_func()
    assert result == expected
```

## Syntax Rules

### Classes

- Use `__slots__` to restrict variables when not using `dataclasses` or `pydantic`

```python
class Foo:
    __slots__ = ("name", "age")

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
```

- Value Objects:
  - Medium-scale or when `dataclasses` fits: use `dataclasses.dataclass(frozen=True)`
  - Large-scale: use `pydantic`
  - When difficult to determine, defer judgment to user
- Basically don't use `@staticmethod` — needing it indicates a design error

### Functions

- Keep functions focused and small
- Use Pythonic syntax (comprehensions, `with` statements, etc.)
- Don't use `global`, `nonlocal` (not explicit enough)

### Strings

#### Quote Usage

- String contains `'` → use `"`
- String contains `"` → use `'`
- f-strings (variable substitution) → use `"`
- `raise` statements → use `"` (normal sentences use `'`)

#### Operators

- Separate operators and operands by one space
- When using 2+ operators, omit spaces around `*`, `/`, `//`, `%`, `**` (higher precedence)

### Logging

Write in dictionary format. Add extensive logging at critical system points where failures
would be hard to diagnose (CSV file references, before/after raise statements, etc.).

```python
logger.info({
    "action": "save",
    "csv_file": self.csv_file,
    "status": "run"
})
```

## Naming Conventions

- Constants: `SCREAMING_SNAKE_CASE`
- Variables / functions / files: `snake_case`
  - Getters: name of the output variable
- Classes: `UpperCamelCase`
- Iterator arguments:
  - Loop body ≤ 2 lines: single character (`x`, `i`)
  - Loop body ≥ 3 lines: descriptive name

## Whitespace & Layout

### Two blank lines before/after

- Import statements
- Global variable definitions
- Object (class/function) definitions

### One blank line between

- Function/method docstring sections: summary `"""`, detail, `Args`, `Returns/Yields`, `Raises`
- Import groups (standard / third-party / local / personal)
- Instance methods

### Indentation

- When handling multiple objects in parallel, align indentation with the previous element

## Comments & Docstrings

- Write comments on their own line above the relevant code
- Always add docstrings to public APIs

```python
# File level
"""Explanation of file functionality"""

# Class & method level
class MyClass:
    """Class functionality explanation"""

    def method(self):
        """Method functionality explanation"""

# Function level
def function_name(arg1, arg2):
    """Function functionality summary.

    (Detailed function functionality.)

    Args:
        arg1 (type): Argument description
        arg2 (type): Argument description

    Returns/Yields:
        type: Return value description

    Raises:
        ErrorType: Error description

    (see details at: URL)
    """
```
