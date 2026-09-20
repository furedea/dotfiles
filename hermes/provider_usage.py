#!/usr/bin/env -S python3 -IB
"""Report plan rate-limit usage for the configured Codex and Claude accounts."""

import base64
from collections.abc import Callable
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CODEX_HOME = Path.home() / ".codex"
CODEX_ACCOUNTS = CODEX_HOME / "accounts"
CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_USER_AGENT = "codex_cli_rs/0.55.0"
CLAUDE_KEYCHAIN_SERVICE = "Claude Code-credentials"
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLAUDE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_USAGE_BETA = "oauth-2025-04-20"
CLAUDE_USER_AGENT = "claude-cli/2.1.276 (external, cli)"
TIMEOUT_SECONDS = 15
EXPIRY_MARGIN_SECONDS = 300

CODEX_WINDOW_LABELS = {18000: "5時間枠", 604800: "週枠"}
CLAUDE_WINDOW_LABELS = {
    "five_hour": "5時間枠",
    "seven_day": "週枠",
    "seven_day_opus": "Opus週枠",
    "seven_day_sonnet": "Sonnet週枠",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, document: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


def post_form(url: str, fields: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


def jwt_expiry(token: str) -> float | None:
    """Return the JWT exp claim as epoch seconds, or None when the token is opaque."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except IndexError, KeyError, ValueError:
        return None


def short_error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, urllib.error.URLError):
        return str(error.reason)
    return str(error)[:80]


def sync_active_account() -> None:
    """Fold the CLI-refreshed ~/.codex/auth.json back into its matching accounts/ file."""
    active_path = CODEX_HOME / "auth.json"
    if not active_path.exists() or not CODEX_ACCOUNTS.is_dir():
        return
    try:
        active = read_json(active_path)
        account_id = active["tokens"]["account_id"]
    except KeyError, json.JSONDecodeError:
        return
    for path in CODEX_ACCOUNTS.glob("*.json"):
        try:
            if read_json(path)["tokens"]["account_id"] == account_id:
                write_json(path, active)
        except KeyError, json.JSONDecodeError:
            continue


def fresh_access_token(path: Path, document: dict) -> str:
    """Return a live access token, refreshing and persisting the account file when expired."""
    tokens = document["tokens"]
    expiry = jwt_expiry(tokens["access_token"])
    if expiry is None or expiry > time.time() + EXPIRY_MARGIN_SECONDS:
        return tokens["access_token"]
    if not tokens.get("refresh_token"):
        return tokens["access_token"]
    refreshed = post_form(
        CODEX_TOKEN_URL,
        {
            "client_id": CODEX_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        {"User-Agent": CODEX_USER_AGENT},
    )
    for key in ("access_token", "refresh_token", "id_token"):
        if refreshed.get(key):
            tokens[key] = refreshed[key]
    write_json(path, document)
    return tokens["access_token"]


def window_label(seconds: int) -> str:
    return CODEX_WINDOW_LABELS.get(seconds, f"{seconds // 3600}時間枠")


def reset_label(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).astimezone().strftime("%-m/%-d %H:%M")


def codex_window_text(window: dict) -> str:
    return (
        f"{window_label(window['limit_window_seconds'])} {window['used_percent']}%"
        f" (reset {reset_label(window['reset_at'])})"
    )


def codex_account_line(path: Path) -> str:
    document = read_json(path)
    tokens = document["tokens"]
    token = fresh_access_token(path, document)
    usage = get_json(
        CODEX_USAGE_URL,
        {
            "Authorization": f"Bearer {token}",
            "ChatGPT-Account-Id": tokens["account_id"],
            "User-Agent": CODEX_USER_AGENT,
        },
    )
    rate_limit = usage.get("rate_limit") or {}
    windows = [
        codex_window_text(window)
        for window in (rate_limit.get("primary_window"), rate_limit.get("secondary_window"))
        if window
    ]
    return f"Codex ({path.stem}): " + ("・".join(windows) if windows else "制限なし")


def percent(value: float) -> int:
    value = float(value)
    return round(value * 100 if value <= 1 else value)


def claude_window_text(name: str, window: dict) -> str:
    label = CLAUDE_WINDOW_LABELS.get(name, name)
    resets_at = window.get("resets_at")
    if resets_at:
        reset = datetime.fromisoformat(resets_at).astimezone().strftime("%-m/%-d %H:%M")
        return f"{label} {percent(window['utilization'])}% (reset {reset})"
    return f"{label} {percent(window['utilization'])}%"


def keychain_item(service: str, flag: str) -> str:
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", service, flag],
        text=True,
        stderr=subprocess.DEVNULL,
    )


def keychain_account(service: str) -> str | None:
    match = re.search(r'"acct"<blob>="([^"]*)"', keychain_item(service, "-g"))
    return match.group(1) if match else None


def write_keychain(service: str, account: str | None, value: str) -> None:
    command = ["security", "add-generic-password", "-U", "-s", service, "-w", value]
    if account:
        command += ["-a", account]
    subprocess.run(command, check=True, capture_output=True)


def claude_fresh_oauth(credentials: dict) -> tuple[dict, str]:
    """Return live OAuth fields and a warning when the Keychain write-back failed."""
    oauth = credentials["claudeAiOauth"]
    expires_at = float(oauth.get("expiresAt", 0)) / 1000
    if expires_at > time.time() + EXPIRY_MARGIN_SECONDS:
        return oauth, ""
    account = keychain_account(CLAUDE_KEYCHAIN_SERVICE)
    if account is None:
        return oauth, " (トークン期限切れ — Keychainのaccount属性が読めずrefreshをスキップ)"
    refreshed = post_form(
        CLAUDE_TOKEN_URL,
        {
            "client_id": CLAUDE_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": oauth["refreshToken"],
        },
        {"User-Agent": CLAUDE_USER_AGENT},
    )
    oauth["accessToken"] = refreshed["access_token"]
    if refreshed.get("refresh_token"):
        oauth["refreshToken"] = refreshed["refresh_token"]
    expires_in = float(refreshed.get("expires_in", 0))
    if expires_in:
        oauth["expiresAt"] = int((time.time() + expires_in) * 1000)
    try:
        write_keychain(CLAUDE_KEYCHAIN_SERVICE, account, json.dumps(credentials))
    except OSError, subprocess.CalledProcessError:
        return oauth, " (警告: Keychainへの書き戻し失敗 — claude CLIの再ログインが必要な可能性)"
    return oauth, ""


def claude_line() -> str:
    credentials = json.loads(keychain_item(CLAUDE_KEYCHAIN_SERVICE, "-w"))
    oauth, warning = claude_fresh_oauth(credentials)
    usage = get_json(
        CLAUDE_USAGE_URL,
        {
            "Authorization": f"Bearer {oauth['accessToken']}",
            "anthropic-beta": CLAUDE_USAGE_BETA,
            "User-Agent": CLAUDE_USER_AGENT,
        },
    )
    windows = [claude_window_text(name, usage[name]) for name in CLAUDE_WINDOW_LABELS if usage.get(name)]
    return "Claude: " + ("・".join(windows) if windows else "制限なし") + warning


def guarded(label: str, collect: Callable[[], str]) -> str:
    try:
        return collect()
    except Exception as error:
        return f"{label}: 取得失敗 — {short_error(error)}"


def report_lines() -> list[str]:
    lines = []
    account_files = sorted(CODEX_ACCOUNTS.glob("*.json")) if CODEX_ACCOUNTS.is_dir() else []
    if account_files:
        sync_active_account()
        for path in account_files:
            lines.append(guarded(f"Codex ({path.stem})", lambda p=path: codex_account_line(p)))
    else:
        lines.append("Codex: ~/.codex/accounts/ 未設定 — 各アカウントのauth.jsonをコピーしてください")
    lines.append(guarded("Claude", claude_line))
    return lines


def main() -> int:
    for line in report_lines():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
