"""The provider-usage reporter must format windows and survive credential states."""

import base64
import json
import time

import pytest
from pathlib import Path

from tests.runtime import load_script_module


usage = load_script_module("hermes/provider_usage.py", "provider_usage")


def jwt(payload: dict) -> str:
    segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"header.{segment.decode()}.signature"


def account_file(tmp_path: Path, account_id: str = "acct-1", **token_overrides: str | None) -> Path:
    tokens = {
        "access_token": jwt({"exp": int(time.time()) + 3600}),
        "refresh_token": "refresh",
        "account_id": account_id,
        "id_token": "id",
    }
    tokens.update(token_overrides)
    path = tmp_path / "lab.json"
    usage.write_json(path, {"tokens": tokens})
    return path


def test_jwt_expiry_reads_the_exp_claim() -> None:
    assert usage.jwt_expiry(jwt({"exp": 123})) == 123.0


def test_jwt_expiry_returns_none_for_opaque_tokens() -> None:
    assert usage.jwt_expiry("not-a-jwt") is None


@pytest.mark.parametrize(
    ("seconds", "label"),
    [(18000, "5時間枠"), (604800, "週枠"), (7200, "2時間枠")],
)
def test_window_label_maps_known_windows(seconds: int, label: str) -> None:
    assert usage.window_label(seconds) == label


@pytest.mark.parametrize(("raw", "expected"), [(0.6, 60), (45.2, 45), (1.0, 100)])
def test_percent_normalizes_fraction_and_whole_values(raw: float, expected: int) -> None:
    assert usage.percent(raw) == expected


def test_codex_window_text_includes_label_percent_and_reset() -> None:
    text = usage.codex_window_text({"limit_window_seconds": 604800, "used_percent": 69, "reset_at": 1790232019})
    assert text.startswith("週枠 69% (reset ")


def test_claude_window_text_uses_named_labels_and_tolerates_missing_reset() -> None:
    assert usage.claude_window_text("five_hour", {"utilization": 0.5}).startswith("5時間枠 50%")
    assert "reset" not in usage.claude_window_text("seven_day", {"utilization": 12})


def test_fresh_access_token_keeps_a_valid_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = account_file(tmp_path)
    monkeypatch.setattr(usage, "post_form", lambda *_a, **_k: pytest.fail("must not refresh"))
    document = usage.read_json(path)
    assert usage.fresh_access_token(path, document) == document["tokens"]["access_token"]


def test_fresh_access_token_refreshes_and_persists_expired_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = account_file(tmp_path, access_token=jwt({"exp": int(time.time()) - 10}))
    monkeypatch.setattr(
        usage,
        "post_form",
        lambda *_a, **_k: {"access_token": "new-access", "refresh_token": "new-refresh"},
    )
    assert usage.fresh_access_token(path, usage.read_json(path)) == "new-access"
    persisted = usage.read_json(path)["tokens"]
    assert persisted["access_token"] == "new-access"
    assert persisted["refresh_token"] == "new-refresh"


def test_fresh_access_token_uses_expired_token_when_no_refresh_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = account_file(tmp_path, access_token=jwt({"exp": 1}), refresh_token=None)
    monkeypatch.setattr(usage, "post_form", lambda *_a, **_k: pytest.fail("cannot refresh"))
    document = usage.read_json(path)
    assert usage.fresh_access_token(path, document) == jwt({"exp": 1})


def test_sync_active_account_updates_only_the_matching_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(usage, "CODEX_HOME", tmp_path)
    monkeypatch.setattr(usage, "CODEX_ACCOUNTS", tmp_path / "accounts")
    lab = tmp_path / "accounts" / "lab.json"
    personal = tmp_path / "accounts" / "personal.json"
    lab.parent.mkdir()
    usage.write_json(lab, {"tokens": {"account_id": "acct-1"}, "stale": True})
    usage.write_json(personal, {"tokens": {"account_id": "acct-2"}, "stale": True})
    active = {"tokens": {"account_id": "acct-1"}, "stale": False}
    usage.write_json(tmp_path / "auth.json", active)

    usage.sync_active_account()

    assert usage.read_json(lab) == active
    assert usage.read_json(personal)["stale"] is True


def test_report_lines_mentions_setup_when_accounts_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(usage, "CODEX_ACCOUNTS", tmp_path / "accounts")
    monkeypatch.setattr(usage, "claude_line", lambda: "Claude: ok")
    assert usage.report_lines() == [
        "Codex: ~/.codex/accounts/ 未設定 — 各アカウントのauth.jsonをコピーしてください",
        "Claude: ok",
    ]


def test_report_lines_isolates_per_account_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    accounts = tmp_path / "accounts"
    accounts.mkdir()
    monkeypatch.setattr(usage, "CODEX_ACCOUNTS", accounts)
    monkeypatch.setattr(usage, "sync_active_account", lambda: None)
    usage.write_json(accounts / "broken.json", {"tokens": {}})
    monkeypatch.setattr(usage, "claude_line", lambda: "Claude: ok")
    (line,) = usage.report_lines()[:1]
    assert line.startswith("Codex (broken): 取得失敗")


def test_claude_fresh_oauth_keeps_unexpired_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = {"accessToken": "a", "expiresAt": (time.time() + 3600) * 1000}
    monkeypatch.setattr(usage, "post_form", lambda *_a, **_k: pytest.fail("must not refresh"))
    assert usage.claude_fresh_oauth({"claudeAiOauth": oauth}) == (oauth, "")


def test_claude_fresh_oauth_skips_refresh_without_keychain_account(monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = {"accessToken": "a", "expiresAt": 0, "refreshToken": "r"}
    monkeypatch.setattr(usage, "keychain_account", lambda _service: None)
    monkeypatch.setattr(usage, "post_form", lambda *_a, **_k: pytest.fail("must not refresh"))
    _, warning = usage.claude_fresh_oauth({"claudeAiOauth": oauth})
    assert "スキップ" in warning


def test_claude_fresh_oauth_refreshes_and_writes_back(monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = {"accessToken": "old", "expiresAt": 0, "refreshToken": "r"}
    credentials = {"claudeAiOauth": oauth}
    monkeypatch.setattr(usage, "keychain_account", lambda _service: "kaito")
    monkeypatch.setattr(
        usage,
        "post_form",
        lambda *_a, **_k: {"access_token": "new", "refresh_token": "r2", "expires_in": 3600},
    )
    written = []
    monkeypatch.setattr(usage, "write_keychain", lambda *args: written.append(args))

    refreshed, warning = usage.claude_fresh_oauth(credentials)

    assert warning == ""
    assert refreshed["accessToken"] == "new"
    assert refreshed["refreshToken"] == "r2"
    assert refreshed["expiresAt"] > time.time() * 1000
    (service, account, payload) = written[0]
    assert (service, account) == (usage.CLAUDE_KEYCHAIN_SERVICE, "kaito")
    assert json.loads(payload)["claudeAiOauth"]["accessToken"] == "new"
