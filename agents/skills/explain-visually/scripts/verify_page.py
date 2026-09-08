#!/usr/bin/env python3
"""Validate and render a self-contained explain-visually HTML artifact."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile


AUTHORITY_METADATA = "explain-visually-authority"
SOURCE_METADATA = "explain-visually-source"
REVISION_METADATA = "explain-visually-revision"
DERIVED_VIEW_AUTHORITY = "derived-view"
DEFAULT_VIEWPORT_HEIGHT = 1200
MIN_VIEWPORT_HEIGHT = 800
MAX_VIEWPORT_HEIGHT = 16_000
VIEWPORT_HEIGHT_PADDING = 40
TEMPLATE_TOKEN_PATTERN = re.compile(r"{{[^{}]+}}")
PAGE_HEIGHT_PATTERN = re.compile(r"data-page-height=[\"'](\d+)[\"']")
CSS_URL_PATTERN = re.compile(r"url\(\s*([\"']?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_IMPORT_PATTERN = re.compile(r"@import\s+([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
SCRIPT_RESOURCE_PATTERN = re.compile(
    r"(?:\bfrom\s+|\bimport\s*\(\s*|\bimport\s+|\bfetch\s*\(\s*)[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
BROWSER_COMMANDS = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
)
BROWSER_PATHS = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
)
RESOURCE_ATTRIBUTES = {
    "audio": ("src",),
    "base": ("href",),
    "iframe": ("src",),
    "img": ("src", "srcset"),
    "link": ("href",),
    "object": ("data",),
    "script": ("src",),
    "source": ("src", "srcset"),
    "video": ("poster", "src"),
}


@dataclass(frozen=True, slots=True)
class _BrowserResult:
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool


class _PageInspector(HTMLParser):
    __slots__ = (
        "_in_script",
        "_in_style",
        "_in_title",
        "external_resources",
        "metadata",
        "script_parts",
        "style_parts",
        "title_parts",
    )

    def __init__(self) -> None:
        super().__init__()
        self.external_resources: list[str] = []
        self.metadata: dict[str, str] = {}
        self.script_parts: list[str] = []
        self.style_parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_script = False
        self._in_style = False
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script":
            self._in_script = True
        if tag == "style":
            self._in_style = True
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = attributes.get("name")
            content = attributes.get("content")
            if name is not None and content is not None:
                self.metadata[name] = content.strip()
        for attribute in RESOURCE_ATTRIBUTES.get(tag, ()):
            value = attributes.get(attribute)
            if value is not None and (attribute == "srcset" or _loads_external_resource(value)):
                self.external_resources.append(f"{tag}[{attribute}]={value}")
        style = attributes.get("style")
        if style is not None:
            self.style_parts.append(style)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False
        if tag == "style":
            self._in_style = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.script_parts.append(data)
        if self._in_style:
            self.style_parts.append(data)
        if self._in_title:
            self.title_parts.append(data)


def validate_html(html: str) -> tuple[str, ...]:
    """Return deterministic validation errors for an explanation page."""
    inspector = _PageInspector()
    inspector.feed(html)
    errors: list[str] = []

    if TEMPLATE_TOKEN_PATTERN.search(html):
        errors.append("The page contains an unresolved template token.")
    if not "".join(inspector.title_parts).strip():
        errors.append("The page must have a non-empty title.")

    required_metadata = {
        AUTHORITY_METADATA: DERIVED_VIEW_AUTHORITY,
        SOURCE_METADATA: None,
        REVISION_METADATA: None,
    }
    for name, expected_value in required_metadata.items():
        actual_value = inspector.metadata.get(name)
        if not actual_value:
            errors.append(f"The page is missing non-empty {name} metadata.")
        elif expected_value is not None and actual_value != expected_value:
            errors.append(f"The {name} metadata must be {expected_value}.")

    for resource in inspector.external_resources:
        errors.append(f"The page loads an external resource: {resource}.")
    for resource in _external_css_resources(inspector.style_parts):
        errors.append(f"The page loads an external resource from CSS: {resource}.")
    for resource in _external_script_resources(inspector.script_parts):
        errors.append(f"The page loads an external resource from JavaScript: {resource}.")

    return tuple(errors)


def find_browser(explicit_browser: str | None = None) -> Path | None:
    """Resolve an executable Chromium-family browser without assuming one provider or OS."""
    configured_browser = explicit_browser or os.environ.get("EXPLAIN_VISUALLY_BROWSER")
    if configured_browser:
        browser = _resolve_executable(configured_browser)
        if browser is None:
            raise FileNotFoundError(f"Browser executable was not found: {configured_browser}")
        return browser

    for command in BROWSER_COMMANDS:
        browser = _resolve_executable(command)
        if browser is not None:
            return browser
    for path in BROWSER_PATHS:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def viewport_height(dom: str) -> tuple[int, str | None]:
    """Return a bounded screenshot height and an optional degradation warning."""
    match = PAGE_HEIGHT_PATTERN.search(dom)
    if match is None:
        return DEFAULT_VIEWPORT_HEIGHT, "The rendered page did not report its height; the default was used."

    requested_height = int(match.group(1)) + VIEWPORT_HEIGHT_PADDING
    bounded_height = max(MIN_VIEWPORT_HEIGHT, min(requested_height, MAX_VIEWPORT_HEIGHT))
    if bounded_height != requested_height:
        return bounded_height, f"The requested screenshot height was clamped to {bounded_height}px."
    return bounded_height, None


def _loads_external_resource(value: str) -> bool:
    return _is_external_reference(value)


def _external_css_resources(styles: Iterable[str]) -> tuple[str, ...]:
    resources: list[str] = []
    for style in styles:
        resources.extend(match[1] for match in CSS_URL_PATTERN.findall(style) if _is_external_reference(match[1]))
        resources.extend(match[1] for match in CSS_IMPORT_PATTERN.findall(style) if _is_external_reference(match[1]))
    return tuple(resources)


def _external_script_resources(scripts: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        resource
        for script in scripts
        for resource in SCRIPT_RESOURCE_PATTERN.findall(script)
        if _is_external_reference(resource)
    )


def _is_external_reference(value: str) -> bool:
    normalized_value = value.strip()
    return bool(normalized_value) and not normalized_value.startswith(("#", "data:"))


def _resolve_executable(value: str) -> Path | None:
    path = Path(value).expanduser()
    if path.is_file() and os.access(path, os.X_OK):
        return path
    resolved = shutil.which(value)
    return Path(resolved) if resolved is not None else None


def _run_browser(browser: Path, arguments: list[str], timeout_seconds: int) -> _BrowserResult:
    process = subprocess.Popen(
        [str(browser), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return _BrowserResult(stdout, stderr, process.returncode, False)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
        return _BrowserResult(stdout, stderr, 124, True)


def _browser_arguments(profile: Path, width: int, wait_ms: int) -> list[str]:
    return [
        "--headless=new",
        "--disable-crash-reporter",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-default-browser-check",
        "--no-first-run",
        f"--user-data-dir={profile}",
        f"--virtual-time-budget={wait_ms}",
        f"--window-size={width},1200",
    ]


def _render_page(
    html_path: Path,
    browser: Path,
    width: int,
    wait_ms: int,
    timeout_seconds: int,
) -> tuple[Path, tuple[str, ...]]:
    warnings: list[str] = []
    page_url = html_path.as_uri()
    screenshot_path = html_path.with_name(f"{html_path.stem}-shot.png")

    with tempfile.TemporaryDirectory(prefix="explain-visually-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        profile = temporary_path / "browser-profile"
        rendered_screenshot_path = temporary_path / "rendered-page.png"
        common_arguments = _browser_arguments(profile, width, wait_ms)
        dom_result = _run_browser(browser, [*common_arguments, "--dump-dom", page_url], timeout_seconds)
        if not dom_result.stdout and dom_result.return_code != 0:
            detail = (
                "browser timed out before producing the rendered DOM"
                if dom_result.timed_out
                else dom_result.stderr.strip() or f"exit status {dom_result.return_code}"
            )
            raise RuntimeError(f"Browser DOM rendering failed: {detail}")

        height, height_warning = viewport_height(dom_result.stdout)
        if height_warning is not None:
            warnings.append(height_warning)

        screenshot_arguments = [
            *common_arguments,
            f"--window-size={width},{height}",
            f"--screenshot={rendered_screenshot_path}",
            page_url,
        ]
        screenshot_result = _run_browser(browser, screenshot_arguments, timeout_seconds)
        if not rendered_screenshot_path.is_file() or rendered_screenshot_path.stat().st_size == 0:
            detail = (
                "browser timed out before producing the screenshot"
                if screenshot_result.timed_out
                else screenshot_result.stderr.strip() or f"exit status {screenshot_result.return_code}"
            )
            raise RuntimeError(f"Browser screenshot failed: {detail}")
        try:
            shutil.copyfile(rendered_screenshot_path, screenshot_path)
        except OSError as error:
            raise RuntimeError(f"Could not store the rendered screenshot: {error}") from error

    return screenshot_path, tuple(warnings)


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="HTML page to validate and render")
    parser.add_argument("--browser", help="browser executable path or command name")
    parser.add_argument("--width", type=int, default=1250, help="screenshot width in pixels")
    parser.add_argument("--wait-ms", type=int, default=2500, help="browser rendering budget in milliseconds")
    parser.add_argument("--timeout-seconds", type=int, default=8, help="browser command timeout")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate, render, and report the artifact in machine-readable JSON."""
    args = _arguments(argv)
    html_path = args.html.expanduser().resolve()
    report: dict[str, object] = {
        "html": str(html_path),
        "mechanicalVerificationComplete": False,
        "rendered": False,
        "staticValid": False,
        "visualInspectionRequired": False,
    }

    if not html_path.is_file():
        report["errors"] = [f"HTML file was not found: {html_path}"]
        print(json.dumps(report, indent=2))
        return 1

    try:
        html = html_path.read_text(encoding="utf-8")
    except UnicodeError as error:
        report["errors"] = [f"HTML file is not valid UTF-8: {error}"]
        print(json.dumps(report, indent=2))
        return 1

    errors = validate_html(html)
    report["staticValid"] = not errors
    if errors:
        report["errors"] = list(errors)
        print(json.dumps(report, indent=2))
        return 1

    try:
        browser = find_browser(args.browser)
    except FileNotFoundError as error:
        report["errors"] = [str(error)]
        print(json.dumps(report, indent=2))
        return 2
    if browser is None:
        report["errors"] = ["No supported browser executable was found. Use --browser or a provider rendering tool."]
        print(json.dumps(report, indent=2))
        return 2

    report["browser"] = str(browser)
    try:
        screenshot_path, warnings = _render_page(
            html_path,
            browser,
            args.width,
            args.wait_ms,
            args.timeout_seconds,
        )
    except RuntimeError as error:
        report["errors"] = [str(error)]
        print(json.dumps(report, indent=2))
        return 1

    report.update(
        {
            "mechanicalVerificationComplete": True,
            "rendered": True,
            "screenshot": str(screenshot_path),
            "visualInspectionRequired": True,
            "warnings": list(warnings),
        }
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
