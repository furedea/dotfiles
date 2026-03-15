# Python Coding Style Guidelines

This document provides coding style guidelines for Python development.

## Package Management

- Use only `uv` for package management, don't use `pip`
- Install packages using `uv add {package}`
- Run tools using `uv run {tool}`
- Upgrade packages using `uv add --dev {package} --upgrade-package {package}`
- Prohibited: `uv pip install`, `@latest`

## Directory Structure

- Store production code including entry points in ./src directory
- Store test code in ./tests directory

## File Standards

- Keep code within 119 characters per line (PEP suggests 79, but we adopt more practical length)
  - URLs may exceed this limit
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

## Syntax Rules

### Classes

- Use `__slots__` to restrict variables when not using `dataclasses` or `pydantic`
- Value Objects:
  - For medium-scale codebases or when `dataclasses` provides better implementation, use `dataclasses.dataclass(frozen=True)`
  - For large-scale codebases, use `pydantic`
  - When difficult to determine, defer judgment to user
- Basically don't use `@staticmethod` as needing it indicates design error

### Functions

- Keep functions focused and small
- Use Pythonic syntax (comprehensions, with statements, ...)
- Don't use `local`, `nonlocal` (not explicit enough)

### Strings

#### Quote Usage

- When string contains `'`: use `"`
- When string contains `"`: use `'`
- When substituting variables in strings (f-strings): use `"`
- In raise statements: use `"` (since normal sentences use `'`)

#### Operators

- Separate operators and objects by one space
- When using 2+ operators, don't add spaces around `*`, `/`, `//`, `%`, `**` (due to higher precedence)

### Logging

#### Basic Policy

- Write in dictionary format
- Add extensive logging in places important to system where troubles would be problematic
  - Examples: CSV file references, before/after raise statements, etc.

#### Example

```python
logger.info({
    "action": "save",
    "csv_file": self.csv_file,
    "status": "run"
})
```

## Naming Conventions

### Basic Principles

- Don't start with numbers

### Naming Patterns

- Constants: `SCREAMING_SNAKE_CASE`
- Variables/functions/files: `snake_case`
  - Getters: name of output variable
- Classes: `UpperCamelCase`
- Iterator arguments:
  - For statements within 2 lines: single character
  - For 3+ lines: descriptive naming

## Whitespace & Layout

### Two blank lines

- Import statements
- Global variable definitions
- Between object definitions

### One blank line

- Between function definition `"""`, `Args`, `Returns/Yields`, `Raises`
- Between standard, third-party, local, personal library imports
- Between instance methods

### Indentation

- When handling multiple objects in parallel, may align indentation with previous element and break lines

## Comments

### Basic Policy

- Write comments independently on their own line when possible

### Documentation

- Always add docstrings to public APIs

#### File Level

```python
"""Explanation of file functionality"""
```

#### Class & Method Level

```python
class MyClass:
    """Class functionality explanation"""

    def method(self):
        """Method functionality explanation"""
```

#### Function Level

```python
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

#### Inline Comments

- Write code intentions above the relevant code
