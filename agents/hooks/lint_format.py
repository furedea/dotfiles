#!/usr/bin/env -S python3 -IB
"""Adapt normalized quality diagnostics to the provider hook contract."""

import json
from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent))
sys.path.insert(0, str(SCRIPT.parent / "lib"))

from lib import formatter_policy, hook_input, lint_engine, process_runner


EXTENSIONS = hook_input.EXTENSIONS
LANGUAGES = frozenset(EXTENSIONS.values())
EDIT_TOOLS = hook_input.EDIT_TOOLS
Step = formatter_policy.Step
ProcessResult = process_runner.ProcessResult
FORMATTED_OUTPUT_LIMIT_BYTES = process_runner.FORMATTED_OUTPUT_LIMIT_BYTES
PROCESS_OUTPUT_LIMIT_BYTES = process_runner.PROCESS_OUTPUT_LIMIT_BYTES
STEP_TIMEOUT_SECONDS = process_runner.STEP_TIMEOUT_SECONDS
NOTIFICATION_LIMIT_BYTES = 16 * 1024
MAX_DIAGNOSTICS = 16


project_root = formatter_policy.project_root
project_files = formatter_policy.project_files
toml_data = formatter_policy.toml_data
dependency_names = formatter_policy.dependency_names
python_project_tool = formatter_policy.python_project_tool
policy_step = formatter_policy.policy_step
plan = formatter_policy.plan
run_process = process_runner.run_process
run_step = lint_engine.run_step
check_file = lint_engine.check_file
replace_formatted_file = lint_engine.replace_formatted_file
target_paths = hook_input.target_paths


def context(message: str) -> dict[str, object]:
    """Encode one provider-compatible PostToolUse context object."""
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}


def diagnostics(payload: dict, kind: str | None = None) -> tuple[str, ...]:
    """Normalize a provider payload before passing it to the shared lint engine."""
    if not isinstance(payload, dict):
        raise TypeError("hook payload must be an object")
    return lint_engine.diagnostics(
        target_paths(payload),
        EXTENSIONS,
        kind,
        checker=check_file,
    )


def emit(messages: tuple[str, ...]) -> None:
    """Write one structured notification for all diagnostics, or remain silent."""
    if messages:
        selected = list(messages[:MAX_DIAGNOSTICS])
        if len(messages) > MAX_DIAGNOSTICS:
            selected.append(f"[diagnostics truncated: {len(messages) - MAX_DIAGNOSTICS} more]")
        message = "\n\n".join(selected)
        marker = "\n[diagnostics truncated]"
        encoded = message.encode()
        if len(encoded) > NOTIFICATION_LIMIT_BYTES:
            budget = NOTIFICATION_LIMIT_BYTES - len(marker.encode())
            head = budget // 2
            tail = budget - head
            message = encoded[:head].decode(errors="ignore") + marker + encoded[-tail:].decode(errors="ignore")
        print(json.dumps(context(message), ensure_ascii=False))


def main(arguments: list[str]) -> int:
    """Run the dispatcher, with an optional language filter kept for direct compatibility."""
    if len(arguments) > 1 or any(value in {"--help", "-h"} for value in arguments):
        print("Usage: lint_format.py [language]", file=sys.stderr)
        return 1
    kind = arguments[0] if arguments else None
    if kind is not None and kind not in LANGUAGES:
        print("Usage: lint_format.py [language]", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("hook payload must be an object")
        values = payload.get("tool_input") or {}
        if kind is not None and isinstance(values, dict) and isinstance(values.get("file_path"), str):
            if not target_paths(payload) or not target_paths(payload)[0].is_file():
                print(f"File not found: {values['file_path']}", file=sys.stderr)
                return 1
        emit(diagnostics(payload, kind))
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
