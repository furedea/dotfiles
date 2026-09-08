"""Extract conservative routing observations without executing transcript content."""

from __future__ import annotations

import ast
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path


CONTEXT_PREFIXES = (
    "# AGENTS.md instructions",
    "<environment_context>",
    "<hook_prompt",
    "<skill>",
    "<turn_aborted>",
    "<subagent_notification",
    "<permissions instructions>",
)
LITERAL_COMMAND = re.compile(r"""(?:["']?(?:cmd|command)["']?)\s*:\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""")


JS_OBJECT = r"""\{(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^{}"'])*\}"""
NESTED_EXEC = re.compile(r"tools\.exec_command\(\s*(" + JS_OBJECT + r")\s*\)")


def collect_session(filepath: str, cutoff: datetime | None = None) -> dict:
    """Stream relevant rows; never treat a read attempt as proof of skill invocation."""
    messages: list[dict] = []
    calls: dict[str, list[dict]] = {}
    errors: list[str] = []
    event_count = 0
    row_count = 0
    with Path(filepath).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"Line {line_number}: invalid JSON")
                continue
            if not isinstance(row, dict):
                errors.append(f"Line {line_number}: expected object")
                continue
            row_count += 1
            event_count += extract_row(row, messages, calls)

    turns = build_turns(messages, use_events=event_count > 0)
    unknown_timestamps = sum(parse_timestamp(turn.get("timestamp")) is None for turn in turns)
    if cutoff is not None:
        turns = [
            turn
            for turn in turns
            if (parse_timestamp(turn.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
        ]
    loaded = list(dict.fromkeys(path for turn in turns for path in turn["skills_loaded_after"]))
    return {
        "session_id": Path(filepath).stem,
        "filepath": filepath,
        "turn_skill_map": turns,
        "skills_loaded": loaded,
        "user_turn_count": len(turns),
        "first_timestamp": turns[0]["timestamp"] if turns else None,
        "last_timestamp": turns[-1]["timestamp"] if turns else None,
        "message_count": row_count,
        "parse_errors": errors,
        "user_turn_basis": "event_msg" if event_count else "response_item_fallback",
        "unknown_timestamp_turns": unknown_timestamps,
        "historical_visibility": "unknown",
    }


def extract_row(row: dict, messages: list[dict], calls: dict[str, list[dict]]) -> int:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return 0
    kind = payload.get("type")
    timestamp = row.get("timestamp")
    if row.get("type") == "event_msg" and kind == "user_message":
        content = text_content(payload.get("message"))
        if content and not content.startswith(CONTEXT_PREFIXES):
            messages.append({"kind": "event_user", "content": content, "timestamp": timestamp})
            return 1
    if row.get("type") != "response_item":
        return 0
    if kind == "message" and payload.get("role") == "user":
        content = text_content(payload.get("content"))
        if content and not content.startswith(CONTEXT_PREFIXES):
            messages.append({"kind": "response_user", "content": content, "timestamp": timestamp})
        elif content.startswith("<skill>"):
            messages.append({"kind": "injected_skill", "names": re.findall(r"<name>([^<]+)</name>", content)})
    elif kind in ("function_call", "custom_tool_call"):
        evidence = read_attempts(payload)
        if evidence:
            calls[str(payload.get("call_id", ""))] = evidence
            messages.append({"kind": "read", "evidence": evidence})
    elif kind in ("function_call_output", "custom_tool_call_output"):
        evidence = calls.pop(str(payload.get("call_id", "")), [])
        if not evidence:
            return 0
        status = result_status(payload.get("output"))
        for item in evidence:
            item["status"] = status if item["result_attributable"] else "unverified"
    return 0


def text_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(item.get("text", "") for item in value if isinstance(item, dict)).strip()
    return ""


def read_attempts(payload: dict) -> list[dict]:
    name = str(payload.get("name", "")).split(".")[-1]
    commands: list[str] = []
    paths: list[str] = []
    attributable = True
    if payload.get("type") == "custom_tool_call" and name == "exec":
        source = str(payload.get("input", ""))
        if "tools.exec_command(" not in source:
            return []
        argument_objects = NESTED_EXEC.findall(source)
        attributable = bool(re.fullmatch(r"\s*text\(\s*await\s*" + NESTED_EXEC.pattern + r"\s*\)\s*;?\s*", source))
        for match in LITERAL_COMMAND.finditer("\n".join(argument_objects)):
            try:
                command = ast.literal_eval(match.group(1))
            except ValueError, SyntaxError:
                continue
            if isinstance(command, str):
                commands.append(command)
    else:
        args = payload.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return []
        if not isinstance(args, dict):
            return []
        if name in ("exec_command", "bash", "bash_tool", "execute_command"):
            commands.append(args.get("cmd", args.get("command", "")))
        elif name in ("Read", "read_file", "view"):
            paths.append(args.get("file_path", args.get("path", "")))
    for command in commands:
        paths.extend(shell_read_paths(command))
    return [
        {
            "path": path,
            "call_id": payload.get("call_id"),
            "status": "unverified",
            "full_read_verified": False,
            "result_attributable": attributable,
        }
        for path in dict.fromkeys(paths)
        if isinstance(path, str) and path.endswith("/SKILL.md")
    ]


def shell_read_paths(command: str) -> list[str]:
    """Recognize literal read commands, not search results or mentioned filenames."""
    paths = []
    for segment in re.split(r"[;\n]|&&|\|\|", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if not tokens or Path(tokens[0]).name not in ("cat", "sed", "head", "tail", "less", "more"):
            continue
        if Path(tokens[0]).name == "sed" and any(token.startswith(("-i", "--in-place")) for token in tokens[1:]):
            continue
        # Dynamic expansions and pipelines cannot be safely attributed statically.
        if any(char in segment for char in ("$", "`", "|", ">", "{", "}", "*", "?")):
            continue
        paths.extend(token for token in tokens[1:] if token.endswith("/SKILL.md"))
    return paths


def result_status(output: object) -> str:
    text = text_content(output)
    try:
        decoded = json.loads(text)
    except ValueError, TypeError:
        decoded = None
    if isinstance(decoded, dict) and isinstance(decoded.get("exit_code"), int):
        return "succeeded" if decoded["exit_code"] == 0 else "failed"
    codes = re.findall(r'(?:"exit_code"\s*:\s*|Process exited with code\s+)(\d+)', text)
    # Multiple nested results are not reliably attributable to individual calls.
    if len(codes) == 1:
        return "succeeded" if codes[0] == "0" else "failed"
    return "unverified"


def build_turns(messages: list[dict], *, use_events: bool) -> list[dict]:
    turns: list[dict] = []
    active = False
    user_kind = "event_user" if use_events else "response_user"
    for message in messages:
        if message["kind"] == user_kind:
            active = True
            turns.append(
                {
                    "turn_index": len(turns),
                    "user_message": message["content"],
                    "timestamp": message["timestamp"],
                    "skills_loaded_after": [],
                    "is_builtin_command": False,
                    "skill_read_evidence": [],
                    "injected_skills": [],
                }
            )
        elif use_events and message["kind"] == "response_user":
            if turns and message["content"] != turns[-1]["user_message"]:
                active = False
        elif active and turns and message["kind"] == "read":
            turns[-1]["skill_read_evidence"].extend(message["evidence"])
        elif active and turns and message["kind"] == "injected_skill":
            turns[-1]["injected_skills"].extend(message["names"])
    for turn in turns:
        # Backward-compatible field includes unverified attempts, not only successes.
        turn["skills_loaded_after"] = list(
            dict.fromkeys(item["path"] for item in turn["skill_read_evidence"] if item["status"] != "failed")
        )
    return turns


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None
