"""Select verification commands from changed paths and explicit project mappings."""

from dataclasses import dataclass
import fnmatch
import json
import os
from pathlib import Path
import re
import tomllib


LANGUAGES = ("bats", "python", "javascript_typescript", "rust")
TARGET_LANGUAGES = {
    ".bats": "bats",
    ".py": "python",
    ".rs": "rust",
    ".js": "javascript_typescript",
    ".jsx": "javascript_typescript",
    ".ts": "javascript_typescript",
    ".tsx": "javascript_typescript",
}


class UnknownTestCommand(ValueError):
    """A JavaScript project has no executable test configuration."""


@dataclass(frozen=True, slots=True)
class Invocation:
    """One runner's arguments and user-visible verification scope."""

    label: str
    scope: str
    arguments: tuple[str, ...]


def load_defaults(path: Path) -> dict:
    """Reject missing or malformed language rules instead of silently skipping verification."""
    try:
        rules = json.loads(path.read_text())
        if not isinstance(rules, dict) or not all(language in rules for language in LANGUAGES):
            raise ValueError("missing languages")
        arrays = {
            "source_extensions",
            "test_dirs",
            "test_patterns",
            "self_test_extensions",
            "self_test_globs",
            "exclude_dirs",
            "project_markers",
            "source_dirs",
            "full_suite_triggers",
        }
        for entry in rules.values():
            if not isinstance(entry, dict) or "source_extensions" not in entry:
                raise ValueError("missing extensions")
            if any(not strings(value) for key, value in entry.items() if key in arrays):
                raise ValueError("invalid rule array")
        return rules
    except (OSError, ValueError) as error:
        raise ValueError(f"Missing or invalid configuration: {path}") from error


def strings(value: object) -> bool:
    """Recognize arrays of nonempty strings at configuration boundaries."""
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def project_targets(
    root: Path, changed: tuple[str, ...]
) -> tuple[dict[str, set[str]], dict[str, set[str]], list[str]]:
    """Resolve explicit mappings and track the changed files each language covers."""
    targets: dict[str, set[str]] = {language: set() for language in LANGUAGES}
    covered: dict[str, set[str]] = {language: set() for language in LANGUAGES}
    path = root / ".agents/hooks/rules/related_test_extensions.json"
    if not path.exists():
        return targets, covered, []
    try:
        mappings = json.loads(path.read_text())
        if not isinstance(mappings, dict) or not all(key and strings(value) for key, value in mappings.items()):
            raise ValueError("Expected an object mapping patterns to arrays of nonempty test paths.")
    except (OSError, ValueError) as error:
        raise ValueError(
            f"Invalid configuration: {path}. Expected an object mapping patterns to arrays of nonempty test paths."
        ) from error
    errors: list[str] = []
    for pattern, paths in mappings.items():
        matched_files = {filename for filename in changed if fnmatch.fnmatchcase(filename, pattern)}
        if not matched_files:
            continue
        for target in paths:
            target = str(Path(target))
            absolute = root / target
            if not absolute.exists():
                errors.append(f"Configured test target does not exist: {target}")
            elif absolute.is_dir():
                targets["bats"].add(target)
                covered["bats"] |= matched_files
            elif language := TARGET_LANGUAGES.get(absolute.suffix):
                targets[language].add(target)
                covered[language] |= matched_files
            else:
                errors.append(f"Unsupported configured test target: {target}")
    return targets, covered, errors


def changed_language(rule: dict, changed: tuple[str, ...]) -> bool:
    """Determine whether a changed filename belongs to a configured source language."""
    return any(path.endswith(extension) for path in changed for extension in rule["source_extensions"])


def is_test(rule: dict, filename: str) -> bool:
    """Recognize a directly changed test without inferring its source stem."""
    return any(filename.endswith(extension) for extension in rule.get("self_test_extensions", ())) or any(
        fnmatch.fnmatchcase(Path(filename).name, pattern) for pattern in rule.get("self_test_globs", ())
    )


def pytest_testpaths(root: Path) -> tuple[str, ...]:
    """Honor the project's declared pytest search paths so stray test copies stay out of verification."""
    try:
        options = tomllib.loads((root / "pyproject.toml").read_text()).get("tool", {}).get("pytest", {})
        declared = options.get("ini_options", {}).get("testpaths")
    except OSError, tomllib.TOMLDecodeError, AttributeError:
        return ()
    return tuple(str(Path(item)) for item in declared) if strings(declared) else ()


def within_dirs(path: str, directories: tuple[str, ...]) -> bool:
    """Decide whether a test path lives under one of the search directories."""
    return any(directory == "." or Path(path).is_relative_to(directory) for directory in directories)


def python_targets(root: Path, rule: dict, changed: tuple[str, ...]) -> tuple[set[str], set[str]]:
    """Search only the declared pytest paths and drop changed tests that live outside them."""
    declared = pytest_testpaths(root)
    if declared:
        rule = {**rule, "test_dirs": declared}
    targets, resolved = matching_tests(root, rule, changed)
    kept = {path for path in targets if within_dirs(path, tuple(rule["test_dirs"]))}
    unresolved = {source for source, matched in resolved.items() if not matched & kept}
    return kept, unresolved


def source_files(rule: dict, changed: tuple[str, ...]) -> set[str]:
    """Return changed executable sources, excluding tests and plain documents."""
    return {
        path
        for path in changed
        if any(path.endswith(extension) for extension in rule["source_extensions"]) and not is_test(rule, path)
    }


def matching_tests(root: Path, rule: dict, changed: tuple[str, ...]) -> tuple[set[str], dict[str, set[str]]]:
    """Find basename matches and map every changed source to its discovered tests."""
    targets = {path for path in changed if is_test(rule, path) and (root / path).is_file()}
    resolved: dict[str, set[str]] = {path: set() for path in source_files(rule, changed)}
    sources_by_stem: dict[str, list[str]] = {}
    for path in resolved:
        sources_by_stem.setdefault(Path(path).stem, []).append(path)
    patterns = {
        pattern.replace("{stem}", stem): stem for pattern in rule.get("test_patterns", ()) for stem in sources_by_stem
    }
    excluded = set(rule.get("exclude_dirs", ())) | {".git"}
    for directory in rule.get("test_dirs", ()):
        for parent, directories, files in os.walk(root / directory):
            directories[:] = [name for name in directories if name not in excluded]
            for filename in files:
                for pattern, stem in patterns.items():
                    if not fnmatch.fnmatchcase(filename, pattern):
                        continue
                    target = str((Path(parent) / filename).relative_to(root))
                    targets.add(target)
                    for source in sources_by_stem[stem]:
                        resolved[source].add(target)
    return targets, resolved


def suite_triggered(rule: dict, changed: tuple[str, ...]) -> bool:
    """Detect configuration changes that require a language's broad verification."""
    return any(
        fnmatch.fnmatchcase(path, pattern) for pattern in rule.get("full_suite_triggers", ()) for path in changed
    )


def language_plan(root: Path, rules: dict, changed: tuple[str, ...]) -> tuple[list[Invocation], list[str]]:
    """Build runner invocations without executing external commands."""
    explicit, covered, errors = project_targets(root, changed)
    invocations: list[Invocation] = []
    for language in LANGUAGES:
        rule = rules[language]
        triggered = suite_triggered(rule, changed)
        affected = changed_language(rule, changed) or triggered
        if not affected and not explicit[language]:
            continue
        if not triggered and not explicit[language] and delegated(rule, changed, covered, language):
            continue
        markers = rule.get("project_markers", ())
        if language == "javascript_typescript":
            markers = ("package.json",)
        if markers and not any((root / name).is_file() for name in markers):
            subject = f"Changed {language} sources" if affected else f"Configured {language} tests"
            errors.append(f"{subject} require a project marker such as {markers[0]}.")
            continue
        matched, unresolved = matching_targets(root, language, rule, changed)
        unresolved -= covered[language]
        targets = explicit[language] | matched
        full = triggered or bool(unresolved and rule.get("fallback_on_unmatched_source"))
        if language == "bats":
            if not (root / "tests").is_dir():
                subject = "Changed shell sources" if affected else "Configured bats tests"
                errors.append(f"{subject} require a tests/ directory.")
                continue
            expanded: set[str] = set()
            for target in targets:
                path = root / target
                if path.is_dir():
                    expanded.update(
                        str(child.relative_to(root))
                        for child in path.glob(f"*.{os.environ.get('BATS_FILE_EXTENSION', 'bats')}")
                        if child.is_file()
                    )
                else:
                    expanded.add(target)
            runner = os.environ.get("RUN_RELATED_TESTS_BATS_BIN", "bats")
            if targets and not expanded:
                errors.append("selected test targets do not exist or contain no tests")
            if full:
                invocations.append(Invocation("bats", "full suite", (runner, "tests/", "--recursive")))
            elif expanded:
                invocations.append(Invocation("bats", f"{len(expanded)} targets", (runner, *sorted(expanded))))
        elif language == "python":
            if full:
                invocations.append(
                    Invocation("pytest", "full suite", ("uv", "run", "--frozen", "pytest", "--no-header", "-q"))
                )
            else:
                scope = f"{len(targets)} files" if targets else "full suite"
                invocations.append(
                    Invocation(
                        "pytest", scope, ("uv", "run", "--frozen", "pytest", "--no-header", "-q", *sorted(targets))
                    )
                )
        elif language == "rust":
            invocations.extend(rust_plan(changed, targets, full, root))
        else:
            invocations.extend(
                javascript_plan(root, changed, targets, rule, triggered=triggered, unresolved=unresolved)
            )
    return invocations, errors


def delegated(rule: dict, changed: tuple[str, ...], covered: dict[str, set[str]], language: str) -> bool:
    """Whether every changed source of a language is explicitly verified by another language's tests."""
    sources = {path for path in changed if any(path.endswith(extension) for extension in rule["source_extensions"])}
    others = set().union(*(files for name, files in covered.items() if name != language))
    return bool(sources) and sources <= others


def matching_targets(root: Path, language: str, rule: dict, changed: tuple[str, ...]) -> tuple[set[str], set[str]]:
    """Return each language's matched tests and the sources that resolve to none."""
    if language == "rust":
        sources = source_files(rule, changed)
        unresolved = {
            path
            for path in sources
            if not path.startswith("tests/") and not (root / "tests" / f"{Path(path).stem}.rs").is_file()
        }
        return set(), unresolved
    if language == "python":
        return python_targets(root, rule, changed)
    targets, resolved = matching_tests(root, rule, changed)
    return targets, {source for source, matched in resolved.items() if not matched}


def rust_plan(changed: tuple[str, ...], explicit: set[str], full: bool, root: Path) -> list[Invocation]:
    """Prefer named integration targets and explicit unit filters, otherwise run the crate."""
    if full:
        return [Invocation("rust", "full suite", ("cargo", "test", "--quiet"))]
    filters = {Path(path).stem for path in explicit if not path.startswith("tests/")}
    targets = {Path(path).stem for path in explicit if path.startswith("tests/")}
    for path in changed:
        if not path.endswith(".rs"):
            continue
        stem = Path(path).stem
        if path.startswith("tests/") or (path.startswith("src/") and (root / "tests" / f"{stem}.rs").is_file()):
            targets.add(stem)
    invocations = [
        Invocation("rust", f"unit filter {stem}", ("cargo", "test", stem, "--quiet")) for stem in sorted(filters)
    ]
    invocations += [
        Invocation("rust", f"integration target {stem}", ("cargo", "test", "--test", stem, "--quiet"))
        for stem in sorted(targets)
    ]
    return invocations or [Invocation("rust", "full suite", ("cargo", "test", "--quiet"))]


def javascript_plan(
    root: Path, changed: tuple[str, ...], targets: set[str], rule: dict, *, triggered: bool, unresolved: set[str]
) -> list[Invocation]:
    """Keep dependency-aware Vitest selection in addition to explicit test targets."""
    package = json.loads((root / "package.json").read_text())
    manager = package.get("packageManager", "").split("@", 1)[0]
    if not manager:
        manager = next(
            (
                name
                for lock, name in (
                    ("pnpm-lock.yaml", "pnpm"),
                    ("yarn.lock", "yarn"),
                    ("bun.lock", "bun"),
                    ("bun.lockb", "bun"),
                )
                if (root / lock).is_file()
            ),
            "npm",
        )
    dependencies = dict(package.get("dependencies") or {}, **(package.get("devDependencies") or {}))
    test_script = (package.get("scripts") or {}).get("test", "")
    runner = next((name for name in ("vitest", "jest") if dependencies.get(name) is not None), "")
    if not runner and re.search(r"(^|\s)node\s+--test(\s|$)", test_script):
        runner = "node"
    prefix = {
        "pnpm": ("pnpm", "exec"),
        "npm": ("npm", "exec", "--"),
        "yarn": ("yarn", "exec"),
        "bun": ("bun", "x"),
    }.get(manager, ("false",))
    if not runner:
        if not test_script:
            raise UnknownTestCommand("test command could not be determined")
        arguments = (manager, "run", "test") if manager == "bun" else (manager, "test")
        return [Invocation(f"{manager} test", "full suite", arguments)]
    arguments = ("node", "--test") if runner == "node" else (*prefix, runner)
    escalate = triggered or bool(unresolved and rule.get("fallback_on_unmatched_source") and runner != "vitest")
    if runner != "vitest":
        if escalate:
            return [Invocation(runner, "full suite", arguments)]
        return [
            Invocation(
                runner, f"{len(targets)} related tests" if targets else "full suite", (*arguments, *sorted(targets))
            )
        ]
    if triggered:
        return [Invocation(runner, "full suite", (*arguments, "run"))]
    invocations: list[Invocation] = []
    if targets:
        invocations.append(Invocation(runner, f"{len(targets)} related tests", (*arguments, "run", *sorted(targets))))
    sources = sorted(
        path
        for path in changed
        if Path(path).suffix in {".js", ".jsx", ".ts", ".tsx"} and not is_test(rule, path) and (root / path).is_file()
    )
    if sources:
        invocations.append(
            Invocation(
                runner,
                f"{len(sources)} changed files",
                (*arguments, "related", "--run", "--passWithNoTests", *sources),
            )
        )
    return invocations or [Invocation(runner, "full suite", (*arguments, "run"))]
