"""Interpret runner evidence without conflating unknown counts and zero execution."""

from dataclasses import dataclass
import re


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass(frozen=True, slots=True)
class Evidence:
    """A runner summary and the number of actual observations, when knowable."""

    summary: str
    executed: int | None


def summarize(label: str, output: str) -> Evidence:
    """Read supported runner output; unrecognized output remains explicitly unknown."""
    lines = ANSI.sub("", output).splitlines()
    if label == "bats":
        return summarize_bats(lines)
    if label == "pytest":
        summaries = [
            line
            for line in lines
            if re.match(r"^[= ]*\d+ (passed|failed|skipped|error|xfailed|xpassed|deselected)", line)
        ]
        if not summaries:
            return Evidence("test count unavailable", None)
        summary = re.sub(r" in [0-9.]+s.*$", "", summaries[-1].strip("= "))
        executed = sum(int(count) for count in re.findall(r"(\d+) (?:passed|failed|xfailed|xpassed)\b", summary))
        return Evidence(re.sub(r", 0 (failed|skipped)", "", summary), executed)
    summaries = [
        line.strip()
        for line in lines
        if re.match(r"^\s*(Tests:|Tests\s+|test result:|# (tests|pass|fail|skipped|todo|cancelled) \d)", line)
    ]
    observed: list[int] = []
    for line in lines:
        if label == "rust" and line.startswith("test result:"):
            observed.append(sum(int(count) for count in re.findall(r"(\d+) (?:passed|failed);", line)))
        elif label in {"vitest", "jest"} and re.match(r"^\s*Tests[:\s]", line):
            observed.append(sum(int(count) for count in re.findall(r"(\d+) (?:passed|failed)\b", line)))
        elif label in {"vitest", "jest"} and re.match(r"^\s*No test (files|suites|tests)?\s*found", line):
            observed.append(0)
        elif label == "node" and (match := re.match(r"^# (?:pass|fail) (\d+)", line)):
            observed.append(int(match[1]))
    return Evidence("; ".join(summaries) or "test count unavailable", sum(observed) if observed else None)


def summarize_bats(lines: list[str]) -> Evidence:
    """Count TAP observations, retaining partial-plan and skipped-test information."""
    planned: int | None = None
    passed = failed = skipped = 0
    for line in lines:
        if match := re.match(r"^1\.\.(\d+)", line):
            planned = int(match[1])
        if not re.match(r"^(not )?ok \d+( |$)", line):
            continue
        if re.search(r"#\s*skip(?:\s|$)", line, re.IGNORECASE):
            skipped += 1
        elif line.startswith("not ok"):
            failed += 1
        else:
            passed += 1
    observed = passed + failed + skipped
    if planned is None and not observed:
        return Evidence("test count unavailable", None)
    summary = f"{passed} passed"
    if failed:
        summary += f", {failed} failed"
    if skipped:
        summary += f", {skipped} skipped"
    if planned is not None and planned != observed:
        summary += f" (partial results; {planned} planned)"
    return Evidence(summary, passed + failed)


def first_error(output: str) -> str:
    """Prefer a runner failure line over its banner without exposing unbounded output."""
    lines = [line for line in ANSI.sub("", output).splitlines() if line.strip()]
    failure = next((line for line in lines if re.match(r"^(not ok \d+|FAILED |E\s+)", line)), None)
    return (failure or next(iter(lines), ""))[:240]
