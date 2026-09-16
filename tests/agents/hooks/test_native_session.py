import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT


HOOK = REPO_ROOT / "agents/hooks/verification_session.py"


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_session_start_registers_before_tools_without_a_launcher(
    provider: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("AGENT_VERIFICATION_RUN", raising=False)
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "source.py").write_text("preexisting edit")
    payload = {"cwd": str(root), "session_id": "session", "source": "startup"}
    for event in ("start", "pre", "stop"):
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(HOOK), provider, event],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert "decision" not in output
        if event == "stop":
            assert "no changes" in output["systemMessage"]
        else:
            assert output == {}
    records = list((tmp_path / "state").glob("agent-harness/verification/*/*/results.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text())["session_id"] == "session"
