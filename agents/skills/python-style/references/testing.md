# Python Testing

Use `tsdd` to decide when to add or reuse tests, which behavior to cover, and the appropriate
verification level. The conventions below govern Python test tooling and structure.

- Use only `pytest` as test framework, do not use `unittest`
- Run tests using `uv run --frozen pytest`
- Use `anyio` for async tests, do not use `asyncio`
- Use `pytest-mock` for mocking (`mocker` fixture), do not use `unittest.mock` directly
- `pytest`, `anyio`, and `pytest-mock` belong in the template's test dependency group
- Record a reproduced defect with `@pytest.mark.xfail(strict=True, reason="...")` and a comment
  naming the condition for removing the marker; `strict=True` fails the run when the test
  unexpectedly passes. Remove the marker in the change that fixes the defect.

## Mutation Testing

Use `mutmut` (3.x) when `tsdd` calls for mutation testing; add it to the test dependency group
only when needed.

- Configure `[tool.mutmut]` in `pyproject.toml` with `source_paths = ["src/"]`
- Scope a run to the changed module with a mutant name pattern:
  `uv run --frozen mutmut run "my_package.my_module*"`
- List survivors with `mutmut results`, inspect one with `mutmut show <mutant>`, or use
  `mutmut browse` to review and retest them
- Mutants and results live in `mutants/`; keep it out of version control

## Test Structure

- **Function-based by default**; class only for namespace grouping or `setup_method`/`teardown_method`
- **`@pytest.fixture`**: shared setup across 2+ tests, external resources, or teardown via `yield`; put in `conftest.py` when shared across files
- **Helper function**: prefer over fixture when arguments need to be passed or setup is lightweight
- **`@pytest.mark.parametrize`**: same logic with different inputs
- **Fixture scope**: default `function`; use `module`/`session` only when setup is expensive
- **Mocking**: use `mocker.patch("mod.func", autospec=True)` — enforces real signature, catches wrong-argument bugs silently missed by plain mocks

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
