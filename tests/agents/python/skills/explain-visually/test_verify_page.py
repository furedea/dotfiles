import json
from pathlib import Path
import stat

import pytest
from pytest_mock import MockerFixture

from tests.agents.python.conftest import REPO_ROOT, load_script_module


verify_page = load_script_module(
    "agents/skills/explain-visually/scripts/verify_page.py",
    "explain_visually_verify_page",
)


VALID_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="explain-visually-authority" content="derived-view">
  <meta name="explain-visually-source" content="https://example.com/pull/42">
  <meta name="explain-visually-revision" content="abc123">
  <title>Example explanation</title>
</head>
<body data-page-height="1200">
  <main><a href="https://example.com/pull/42">Source</a></main>
</body>
</html>
"""


def test_validate_html_accepts_self_contained_page_with_external_source_link() -> None:
    assert verify_page.validate_html(VALID_HTML) == ()


@pytest.mark.parametrize(
    "resource",
    [
        '<script src="https://cdn.example.com/app.js"></script>',
        '<script src="app.js"></script>',
        '<link rel="stylesheet" href="https://cdn.example.com/app.css">',
        '<link rel="stylesheet" href="app.css">',
        '<img src="https://cdn.example.com/diagram.png" alt="diagram">',
        '<img src="diagram.png" alt="diagram">',
        '<style>.diagram { background: url("https://cdn.example.com/bg.png"); }</style>',
        '<style>.diagram { background: url("bg.png"); }</style>',
        '<script type="module">import value from "./value.js";</script>',
    ],
)
def test_validate_html_rejects_externally_loaded_resources(resource: str) -> None:
    html = VALID_HTML.replace("</head>", f"{resource}</head>")

    errors = verify_page.validate_html(html)

    assert any("external resource" in error for error in errors)


def test_validate_html_allows_embedded_resources_and_source_examples() -> None:
    content = """
      <style>.diagram { background: url("data:image/svg+xml;base64,PHN2Zz4="); }</style>
    """
    body = """<main>
      <a href="https://example.com/source">Source</a>
      <img src="data:image/png;base64,iVBORw0KGgo=">
      <pre><code>fetch(&quot;https://example.com/data&quot;)</code></pre>
    </main>"""
    html = VALID_HTML.replace("</head>", f"{content}</head>").replace(
        '<main><a href="https://example.com/pull/42">Source</a></main>',
        body,
    )

    assert verify_page.validate_html(html) == ()


def test_validate_html_rejects_unresolved_template_tokens() -> None:
    errors = verify_page.validate_html(VALID_HTML.replace("Example explanation", "{{TITLE}}"))

    assert any("template token" in error for error in errors)


def test_validate_html_requires_authority_source_and_revision_metadata() -> None:
    html = VALID_HTML.replace('<meta name="explain-visually-revision" content="abc123">', "")

    errors = verify_page.validate_html(html)

    assert any("explain-visually-revision" in error for error in errors)


def test_bundled_template_is_self_contained_after_tokens_are_replaced() -> None:
    template_path = REPO_ROOT / "agents/skills/explain-visually/assets/template.html"
    html = template_path.read_text(encoding="utf-8")
    replacements = {
        "{{BODY}}": "<section><h2>Overview</h2><p>Verified content.</p></section>",
        "{{LANG}}": "en",
        "{{REVISION}}": "abc123",
        "{{SOURCE}}": "https://example.com/pull/42",
        "{{TITLE}}": "Example explanation",
    }
    for token, value in replacements.items():
        html = html.replace(token, value)

    assert verify_page.validate_html(html) == ()


def test_find_browser_accepts_an_explicit_executable(tmp_path: Path) -> None:
    browser = tmp_path / "browser"
    browser.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    browser.chmod(browser.stat().st_mode | stat.S_IXUSR)

    assert verify_page.find_browser(str(browser)) == browser


def test_find_browser_rejects_a_missing_explicit_browser(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Browser executable was not found"):
        verify_page.find_browser(str(tmp_path / "missing-browser"))


def test_main_reports_mechanical_verification_without_claiming_visual_inspection(
    tmp_path: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    html_path = tmp_path / "page.html"
    html_path.write_text(VALID_HTML, encoding="utf-8")
    browser = tmp_path / "browser"
    browser.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    browser.chmod(browser.stat().st_mode | stat.S_IXUSR)

    def run_browser(_browser: Path, arguments: list[str], _timeout_seconds: int) -> object:
        if "--dump-dom" in arguments:
            return verify_page._BrowserResult('<body data-page-height="1200">', "", 124, True)
        screenshot_argument = next(argument for argument in arguments if argument.startswith("--screenshot="))
        Path(screenshot_argument.partition("=")[2]).write_bytes(b"\x89PNG\r\n\x1a\n")
        return verify_page._BrowserResult("", "", 124, True)

    mocker.patch.object(verify_page, "_run_browser", autospec=True, side_effect=run_browser)

    exit_code = verify_page.main([str(html_path), "--browser", str(browser)])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "complete" not in report
    assert report["mechanicalVerificationComplete"] is True
    assert report["rendered"] is True
    assert report["visualInspectionRequired"] is True
    assert report["warnings"] == []


def test_main_does_not_accept_a_stale_screenshot_as_render_evidence(
    tmp_path: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    html_path = tmp_path / "page.html"
    html_path.write_text(VALID_HTML, encoding="utf-8")
    html_path.with_name("page-shot.png").write_bytes(b"stale screenshot")
    browser = tmp_path / "browser"
    browser.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    browser.chmod(browser.stat().st_mode | stat.S_IXUSR)

    def run_browser(_browser: Path, arguments: list[str], _timeout_seconds: int) -> object:
        if "--dump-dom" in arguments:
            return verify_page._BrowserResult('<body data-page-height="1200">', "", 0, False)
        return verify_page._BrowserResult("", "render failed", 1, False)

    mocker.patch.object(verify_page, "_run_browser", autospec=True, side_effect=run_browser)

    exit_code = verify_page.main([str(html_path), "--browser", str(browser)])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert report["mechanicalVerificationComplete"] is False
    assert any("screenshot failed" in error.lower() for error in report["errors"])


def test_viewport_height_uses_reported_page_height_within_bounds() -> None:
    assert verify_page.viewport_height('<body data-page-height="2400">') == (2440, None)


@pytest.mark.parametrize(
    ("reported_height", "expected_height"),
    [
        (100, 800),
        (50_000, 16_000),
    ],
)
def test_viewport_height_clamps_unsafe_sizes(reported_height: int, expected_height: int) -> None:
    height, warning = verify_page.viewport_height(f'<body data-page-height="{reported_height}">')

    assert height == expected_height
    assert warning is not None
