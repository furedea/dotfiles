# Python Code Conventions

## Functions

- Keep functions focused and small
- Use Pythonic syntax (comprehensions, `with` statements, etc.)
- Don't use `global`, `nonlocal` (not explicit enough)
- Use built-in generics (e.g., `tuple`, `list`, `dict`) instead of `typing.Tuple`, `typing.List`, `typing.Dict`

## Strings

### Quote Usage

- String contains `'` → use `"`
- String contains `"` → use `'`
- f-strings (variable substitution) → use `"`
- `raise` statements → use `"` (normal sentences use `'`)

### Operators

- Separate operators and operands by one space
- When using 2+ operators, omit spaces around `*`, `/`, `//`, `%`, `**` (higher precedence)

## Logging

Write in dictionary format. Add extensive logging at critical system points where failures would be hard to diagnose (CSV file references, before/after raise statements, etc.).

```python
logger.info({"action": "save", "csv_file": self.csv_file, "status": "run"})
```

## Naming Conventions

- Constants: `SCREAMING_SNAKE_CASE` — define semantically meaningful string literals as module-level constants (two blank lines after imports) rather than embedding them inline
- Variables / functions / files: `snake_case`
    - Getters: name of the output variable
- Classes: `UpperCamelCase`
- Iterator arguments:
    - Loop body ≤ 2 lines: single character (`x`, `i`)
    - Loop body ≥ 3 lines: descriptive name

### File Naming

- Name files after the **domain/action** they represent, not the role suffix
    - Prefer `retrieval.py` over `retriever.py`, `prompt.py` over `prompt_builder.py`
    - `-er`/`-or` suffixes belong on **class names** (e.g. `class Retriever`), not file names
- Avoid `utils.py` / `helpers.py` — name by what the module actually does (e.g. `model.py`, `inference.py`)

## Whitespace & Layout

### Two blank lines before/after

- Import statements
- Global variable definitions
- Object (class/function) definitions

### One blank line between

- Function/method docstring sections: summary `"""`, detail, `Args`, `Returns/Yields`, `Raises`
- Import groups (standard / third-party / local / personal)
- Instance methods

### Imports

- Order import groups as: standard library → third-party → local
- Use exactly one blank line between these groups
- Avoid `from ... import ...` unless the imported name is self-explanatory (e.g., `Enum`, `Path`), or the module path is so long that `module.name` at call sites becomes unwieldy (e.g., `from swebench.inference.make_datasets.utils import extract_diff`)
- Avoid `as` aliases unless required for clarity

### Indentation

- When handling multiple objects in parallel, align indentation with the previous element

### Line Breaks

- One element per line for lists/dicts with 3+ items or long expressions; trailing comma on last element
- Don't sacrifice readability for brevity

```python
# Good
sections = [
    problem_statement,
    *_file_sections(files),
    "Please output a unified diff patch.",
]

# Bad
sections = [problem_statement, *_file_sections(files), "Please output a unified diff patch."]
```

## Comments & Docstrings

- Write comments on their own line above the relevant code
- Always add docstrings to public APIs
- Comment non-obvious choices (algorithm params, fallback behavior, encoding handling)

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
