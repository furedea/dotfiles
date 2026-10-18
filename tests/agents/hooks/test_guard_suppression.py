"""Adding a lint or type-check suppression to code is the user's call, never an agent's shortcut."""

from pathlib import Path

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_suppression.py", "guard_suppression")


def decide(tool: str, values: dict) -> str:
    return guard.decide({"tool_name": tool, "tool_input": values}).decision


@pytest.mark.parametrize(
    "path,text",
    [
        ("src/app.py", "def f(a, b, c, d):  # noqa: PLR0913 -- wraps a fixed C API"),
        ("src/app.py", "value = cast(x)  # type: ignore[arg-type]"),
        ("src/app.ts", "// oxlint-disable-next-line max-params -- mirrors the DOM API"),
        ("src/app.ts", "// @ts-expect-error -- third-party types are wrong"),
        ("src/lib.rs", '#[expect(clippy::too_many_arguments, reason = "FFI signature")]'),
        ("src/lib.rs", "#![allow(clippy::pedantic)]"),
    ],
)
def test_a_new_suppression_in_code_asks(path: str, text: str) -> None:
    assert decide("Edit", {"file_path": path, "old_string": "x = 1", "new_string": f"x = 1\n{text}"}) == "ask"


def test_a_write_that_adds_a_suppression_asks(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("import os  # noqa: F401\n")
    content = "import os  # noqa: F401\nimport sys  # noqa: F401\n"
    assert decide("Write", {"file_path": str(target), "content": content}) == "ask"


@pytest.mark.parametrize(
    "tool,values",
    [
        (
            "Edit",
            {"file_path": "src/app.py", "old_string": "a = 1  # noqa: E501", "new_string": "b = 1  # noqa: E501"},
        ),
        ("Edit", {"file_path": "src/app.py", "old_string": "a = 1  # noqa: E501", "new_string": "a = 1"}),
        ("Edit", {"file_path": "docs/lint.md", "old_string": "x", "new_string": "Use `# noqa: E501` sparingly."}),
        ("Edit", {"file_path": "src/app.py", "old_string": "x = 1", "new_string": "x = 2"}),
    ],
    ids=["moved, not added", "removed", "prose, not code", "no suppression"],
)
def test_edits_that_do_not_add_a_suppression_pass(tool: str, values: dict) -> None:
    assert decide(tool, values) == "allow"


def test_an_apply_patch_that_adds_a_suppression_asks() -> None:
    patch = (
        "*** Begin Patch\n*** Update File: src/app.py\n@@\n-def f(a, b, c, d):\n"
        "+def f(a, b, c, d):  # noqa: PLR0913 -- legacy\n*** End Patch"
    )
    assert decide("apply_patch", {"input": patch}) == "ask"


def test_the_reason_names_the_file_and_the_suppression() -> None:
    verdict = guard.decide(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/app.py", "old_string": "", "new_string": "x  # noqa"}}
    )
    assert "src/app.py" in verdict.reason
    assert "noqa" in verdict.reason
