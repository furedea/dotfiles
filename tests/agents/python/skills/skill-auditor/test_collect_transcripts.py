import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.agents.python.conftest import load_script_module


collect_transcripts = load_script_module(
    "agents/skills/skill-auditor/scripts/collect_transcripts.py",
    "skill_auditor_collect_transcripts",
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_codex_provider_collects_turns_and_skill_loads_for_matching_cwd(tmp_path: Path) -> None:
    session_root = tmp_path / "sessions"
    project_path = tmp_path / "project"
    other_project_path = tmp_path / "other"
    skill_path = tmp_path / "skills" / "python-style" / "SKILL.md"

    write_jsonl(
        session_root / "2026" / "05" / "04" / "rollout-a.jsonl",
        [
            {
                "timestamp": "2026-05-04T09:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": "session-a",
                    "timestamp": "2026-05-04T09:00:00Z",
                    "cwd": str(project_path),
                },
            },
            {
                "timestamp": "2026-05-04T09:01:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Python code を書いて"}],
                },
            },
            {
                "timestamp": "2026-05-04T09:02:00Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": f"sed -n '1,20p' {skill_path}"}),
                },
            },
        ],
    )
    write_jsonl(
        session_root / "2026" / "05" / "04" / "rollout-b.jsonl",
        [
            {
                "timestamp": "2026-05-04T09:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": "session-b",
                    "timestamp": "2026-05-04T09:00:00Z",
                    "cwd": str(other_project_path),
                },
            },
            {
                "timestamp": "2026-05-04T09:01:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "unrelated"}],
                },
            },
        ],
    )

    result = collect_transcripts.collect(
        str(project_path),
        days=0,
        provider="codex",
        session_root=str(session_root),
    )

    assert result["summary"]["total_sessions"] == 1
    session = result["sessions"][0]
    assert session["session_id"] == "session-a"
    assert session["project_dir"] == str(project_path)
    assert session["skills_loaded"] == [str(skill_path)]
    assert [
        {key: turn[key] for key in ("turn_index", "user_message", "skills_loaded_after", "is_builtin_command")}
        for turn in session["turn_skill_map"]
    ] == [
        {
            "turn_index": 0,
            "user_message": "Python code を書いて",
            "skills_loaded_after": [str(skill_path)],
            "is_builtin_command": False,
        }
    ]


def test_codex_provider_collects_all_sessions_recursively(tmp_path: Path) -> None:
    session_root = tmp_path / "sessions"
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"

    for project_path, filename in (
        (project_a, "2026/05/04/rollout-a.jsonl"),
        (project_b, "2026/05/03/rollout-b.jsonl"),
    ):
        write_jsonl(
            session_root / filename,
            [
                {
                    "timestamp": "2026-05-04T09:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": filename,
                        "timestamp": "2026-05-04T09:00:00Z",
                        "cwd": str(project_path),
                    },
                },
                {
                    "timestamp": "2026-05-04T09:01:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "hello"}],
                    },
                },
            ],
        )

    result = collect_transcripts.collect(
        "all",
        days=0,
        provider="codex",
        session_root=str(session_root),
    )

    assert result["summary"]["total_sessions"] == 2
    assert result["summary"]["sessions_by_project"] == {
        str(project_a): 1,
        str(project_b): 1,
    }


def codex_row(payload: dict, timestamp: str = "2026-05-04T09:01:00Z", row_type: str = "response_item") -> dict:
    return {"type": row_type, "timestamp": timestamp, "payload": payload}


def collect_rows(tmp_path: Path, rows: list[dict], days: int = 0) -> dict:
    write_jsonl(
        tmp_path / "session.jsonl", [codex_row({"id": "test", "cwd": str(tmp_path)}, row_type="session_meta"), *rows]
    )
    return collect_transcripts.collect("all", days=days, provider="codex", session_root=str(tmp_path))


def test_codex_nested_reads_preserve_attempts_and_result_evidence(tmp_path: Path) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "Write Python tests"}),
            codex_row(
                {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "call_id": "read",
                    "input": 'text(await tools.exec_command({cmd:"cat /skills/python-style/SKILL.md /skills/tsdd/SKILL.md"}));',
                }
            ),
            codex_row(
                {
                    "type": "custom_tool_call_output",
                    "call_id": "read",
                    "output": [
                        {"type": "input_text", "text": json.dumps({"exit_code": 0, "output": "skill contents"})}
                    ],
                }
            ),
            codex_row(
                {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "call_id": "search",
                    "input": 'text(await tools.exec_command({cmd:"rg SKILL.md /skills"}));',
                }
            ),
            codex_row(
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "failed",
                    "arguments": json.dumps({"cmd": "cat /skills/missing/SKILL.md"}),
                }
            ),
            codex_row(
                {
                    "type": "function_call_output",
                    "call_id": "failed",
                    "output": "Process exited with code 1\ncat: No such file or directory",
                }
            ),
        ],
    )
    turn = result["sessions"][0]["turn_skill_map"][0]
    assert turn["skills_loaded_after"] == ["/skills/python-style/SKILL.md", "/skills/tsdd/SKILL.md"]
    assert [item["status"] for item in turn["skill_read_evidence"]] == ["succeeded", "succeeded", "failed"]


def test_codex_user_events_exclude_replayed_history_and_context(tmp_path: Path) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "Old forked request"}),
            codex_row({"type": "message", "role": "user", "content": "# AGENTS.md instructions\nRules"}),
            codex_row({"type": "user_message", "message": "Implement this"}, row_type="event_msg"),
            codex_row({"type": "message", "role": "user", "content": "Implement this"}),
            codex_row({"type": "message", "role": "user", "content": "<hook_prompt>Passed</hook_prompt>"}),
        ],
    )
    assert result["summary"]["total_user_turns"] == 1
    assert result["sessions"][0]["turn_skill_map"][0]["user_message"] == "Implement this"


def test_codex_date_window_keeps_recent_turn_in_resumed_session(tmp_path: Path) -> None:
    recent = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "Old request"}, old),
            codex_row({"type": "message", "role": "user", "content": "Recent request"}, recent),
        ],
        days=14,
    )
    assert result["summary"]["total_sessions"] == 1
    assert [turn["user_message"] for turn in result["sessions"][0]["turn_skill_map"]] == ["Recent request"]


@pytest.mark.parametrize(
    "command",
    [
        "rg SKILL.md /skills",
        "echo cat /skills/tsdd/SKILL.md",
        "sed -i s/a/b/ /skills/tsdd/SKILL.md",
        "cat $skill_root/tsdd/SKILL.md",
        "cat /skills/tsdd/SKILL.md > /tmp/copy",
    ],
)
def test_codex_nonliteral_or_nonreading_commands_are_not_loads(tmp_path: Path, command: str) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "Inspect the repository"}),
            codex_row(
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "test",
                    "arguments": json.dumps({"cmd": command}),
                }
            ),
        ],
    )
    assert result["sessions"][0]["skills_loaded"] == []


def test_codex_missing_result_and_injected_skill_are_not_automatic_fire_proof(tmp_path: Path) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "$tsdd"}),
            codex_row({"type": "message", "role": "user", "content": "<skill><name>tsdd</name>body</skill>"}),
            codex_row(
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "read",
                    "arguments": json.dumps({"cmd": "head -10 /skills/tsdd/SKILL.md"}),
                }
            ),
        ],
    )
    session = result["sessions"][0]
    assert session["user_turn_count"] == 1
    assert session["historical_visibility"] == "unknown"
    turn = session["turn_skill_map"][0]
    assert turn["injected_skills"] == ["tsdd"]
    assert turn["skill_read_evidence"][0]["status"] == "unverified"
    assert turn["skill_read_evidence"][0]["full_read_verified"] is False


def test_codex_ignores_command_examples_outside_nested_tool_arguments(tmp_path: Path) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "Inspect"}),
            codex_row(
                {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "call_id": "read",
                    "input": 'const example={cmd:"cat /skills/tsdd/SKILL.md"}; text(await tools.exec_command({cmd:"pwd"}));',
                }
            ),
        ],
    )
    assert result["sessions"][0]["skills_loaded"] == []


def test_codex_unmatched_response_user_blocks_previous_turn_read_attribution(tmp_path: Path) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "user_message", "message": "First task"}, row_type="event_msg"),
            codex_row({"type": "message", "role": "user", "content": "First task"}),
            codex_row({"type": "message", "role": "user", "content": "Second task"}),
            codex_row(
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "read",
                    "arguments": json.dumps({"cmd": "cat /skills/tsdd/SKILL.md"}),
                }
            ),
        ],
    )
    assert result["sessions"][0]["turn_skill_map"][0]["skills_loaded_after"] == []


def test_codex_nested_partial_output_does_not_verify_all_calls(tmp_path: Path) -> None:
    result = collect_rows(
        tmp_path,
        [
            codex_row({"type": "message", "role": "user", "content": "Read skills"}),
            codex_row(
                {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "call_id": "read",
                    "input": 'await tools.exec_command({cmd:"cat /skills/tsdd/SKILL.md"}); text(await tools.exec_command({cmd:"pwd"}));',
                }
            ),
            codex_row(
                {
                    "type": "custom_tool_call_output",
                    "call_id": "read",
                    "output": json.dumps({"exit_code": 0, "output": "/tmp"}),
                }
            ),
        ],
    )
    assert result["sessions"][0]["turn_skill_map"][0]["skill_read_evidence"][0]["status"] == "unverified"
