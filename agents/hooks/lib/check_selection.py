"""Select verification commands from changed paths and explicit project mappings."""

from collections.abc import Iterator
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


@dataclass(frozen=True, slots=True)
class LanguageScope:
    """One language's rule and the changed paths it must verify."""

    language: str
    rule: dict
    root: Path
    changed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Selection:
    """A language's resolved test targets and the reasons to widen them."""

    scope: LanguageScope
    targets: frozenset[str]
    unresolved: frozenset[str]
    triggered: bool
    affected: bool

    @property
    def full(self) -> bool:
        """Whether the language's whole suite must run instead of the selected targets."""
        return self.triggered or bool(self.unresolved and self.scope.rule.get("fallback_on_unmatched_source"))


RULE_ARRAYS = {
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
PYTEST = ("uv", "run", "--frozen", "pytest", "--no-header", "-q")
RUST_FULL_SUITE = Invocation("rust", "full suite", ("cargo", "test", "--quiet"))
RUNNER_PREFIXES = {
    "pnpm": ("pnpm", "exec"),
    "npm": ("npm", "exec", "--"),
    "yarn": ("yarn", "exec"),
    "bun": ("bun", "x"),
}
LOCKFILE_MANAGERS = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lock", "bun"),
    ("bun.lockb", "bun"),
)


def load_defaults(path: Path) -> dict:
    """Reject missing or malformed language rules instead of silently skipping verification."""
    try:
        rules = json.loads(path.read_text())
        if not isinstance(rules, dict) or not all(language in rules for language in LANGUAGES):
            raise ValueError("missing languages")
        for entry in rules.values():
            validate_rule(entry)
        return rules
    except (OSError, ValueError) as error:
        raise ValueError(f"Missing or invalid configuration: {path}") from error


def validate_rule(entry: object) -> None:
    """Reject a language rule without source extensions or with malformed arrays."""
    if not isinstance(entry, dict) or "source_extensions" not in entry:
        raise ValueError("missing extensions")
    if any(not strings(value) for key, value in entry.items() if key in RULE_ARRAYS):
        raise ValueError("invalid rule array")


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
    for target, matched_files in mapped_targets(mappings, changed):
        language, error = target_language(root, target)
        if error:
            errors.append(error)
            continue
        targets[language].add(target)
        covered[language] |= matched_files
    return targets, covered, errors


def mapped_targets(mappings: dict, changed: tuple[str, ...]) -> Iterator[tuple[str, set[str]]]:
    """Yield each configured test path with the changed files its pattern matches."""
    for pattern, paths in mappings.items():
        matched_files = {filename for filename in changed if fnmatch.fnmatchcase(filename, pattern)}
        if not matched_files:
            continue
        for target in paths:
            yield str(Path(target)), matched_files


def target_language(root: Path, target: str) -> tuple[str, str]:
    """Classify a configured test path as its runner language, or explain why it cannot run."""
    absolute = root / target
    if not absolute.exists():
        return "", f"Configured test target does not exist: {target}"
    if absolute.is_dir():
        return "bats", ""
    if language := TARGET_LANGUAGES.get(absolute.suffix):
        return language, ""
    return "", f"Unsupported configured test target: {target}"


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
    matches = [
        (str(path.relative_to(root)), stem)
        for path in searched_files(root, rule)
        for pattern, stem in patterns.items()
        if fnmatch.fnmatchcase(path.name, pattern)
    ]
    for target, stem in matches:
        targets.add(target)
        for source in sources_by_stem[stem]:
            resolved[source].add(target)
    return targets, resolved


def searched_files(root: Path, rule: dict) -> Iterator[Path]:
    """Walk the rule's test directories, pruning excluded directories."""
    excluded = set(rule.get("exclude_dirs", ())) | {".git"}
    for directory in rule.get("test_dirs", ()):
        for parent, directories, files in os.walk(root / directory):
            directories[:] = [name for name in directories if name not in excluded]
            yield from (Path(parent) / filename for filename in files)


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
        scope = LanguageScope(language, rules[language], root, changed)
        language_invocations, language_errors = scope_plan(scope, explicit[language], covered)
        invocations.extend(language_invocations)
        errors.extend(language_errors)
    return invocations, errors


def scope_plan(
    scope: LanguageScope, explicit: set[str], covered: dict[str, set[str]]
) -> tuple[list[Invocation], list[str]]:
    """Plan one language unless no change reaches it or another language already verifies it."""
    triggered = suite_triggered(scope.rule, scope.changed)
    affected = changed_language(scope.rule, scope.changed) or triggered
    if not affected and not explicit:
        return [], []
    if not triggered and not explicit and delegated(scope, covered):
        return [], []
    if error := missing_marker(scope, affected=affected):
        return [], [error]
    matched, unresolved = matching_targets(scope)
    selection = Selection(
        scope,
        frozenset(explicit | matched),
        frozenset(unresolved - covered[scope.language]),
        triggered=triggered,
        affected=affected,
    )
    return selection_plan(selection)


def selection_plan(selection: Selection) -> tuple[list[Invocation], list[str]]:
    """Dispatch a resolved selection to its language's runner."""
    match selection.scope.language:
        case "bats":
            return bats_plan(selection)
        case "python":
            return [python_invocation(selection)], []
        case "rust":
            return rust_plan(selection), []
        case _:
            return javascript_plan(selection), []


def delegated(scope: LanguageScope, covered: dict[str, set[str]]) -> bool:
    """Whether every changed source of a language is explicitly verified by another language's tests."""
    sources = {
        path
        for path in scope.changed
        if any(path.endswith(extension) for extension in scope.rule["source_extensions"])
    }
    others = set().union(*(files for name, files in covered.items() if name != scope.language))
    return bool(sources) and sources <= others


def missing_marker(scope: LanguageScope, *, affected: bool) -> str:
    """Explain a missing project marker, or return an empty string when the project is recognizable."""
    markers = ("package.json",) if scope.language == "javascript_typescript" else scope.rule.get("project_markers", ())
    if not markers or any((scope.root / name).is_file() for name in markers):
        return ""
    subject = f"Changed {scope.language} sources" if affected else f"Configured {scope.language} tests"
    return f"{subject} require a project marker such as {markers[0]}."


def matching_targets(scope: LanguageScope) -> tuple[set[str], set[str]]:
    """Return each language's matched tests and the sources that resolve to none."""
    root, rule, changed = scope.root, scope.rule, scope.changed
    if scope.language == "rust":
        sources = source_files(rule, changed)
        unresolved = {
            path
            for path in sources
            if not path.startswith("tests/") and not (root / "tests" / f"{Path(path).stem}.rs").is_file()
        }
        return set(), unresolved
    if scope.language == "python":
        return python_targets(root, rule, changed)
    targets, resolved = matching_tests(root, rule, changed)
    return targets, {source for source, matched in resolved.items() if not matched}


def bats_plan(selection: Selection) -> tuple[list[Invocation], list[str]]:
    """Run whole bats directories non-recursively, or the full suite when escalated."""
    root = selection.scope.root
    if not (root / "tests").is_dir():
        subject = "Changed shell sources" if selection.affected else "Configured bats tests"
        return [], [f"{subject} require a tests/ directory."]
    expanded = expanded_bats_targets(root, selection.targets)
    errors = ["selected test targets do not exist or contain no tests"] if selection.targets and not expanded else []
    runner = os.environ.get("RUN_RELATED_TESTS_BATS_BIN", "bats")
    if selection.full:
        return [Invocation("bats", "full suite", (runner, "tests/", "--recursive"))], errors
    if expanded:
        return [Invocation("bats", f"{len(expanded)} targets", (runner, *sorted(expanded)))], errors
    return [], errors


def expanded_bats_targets(root: Path, targets: frozenset[str]) -> set[str]:
    """Replace directory targets with the bats files directly inside them."""
    expanded: set[str] = set()
    for target in targets:
        path = root / target
        if not path.is_dir():
            expanded.add(target)
            continue
        expanded.update(
            str(child.relative_to(root))
            for child in path.glob(f"*.{os.environ.get('BATS_FILE_EXTENSION', 'bats')}")
            if child.is_file()
        )
    return expanded


def python_invocation(selection: Selection) -> Invocation:
    """Run the selected pytest files, or the full suite when nothing narrower is known."""
    targets = selection.targets
    if selection.full:
        return Invocation("pytest", "full suite", PYTEST)
    scope = f"{len(targets)} files" if targets else "full suite"
    return Invocation("pytest", scope, (*PYTEST, *sorted(targets)))


def rust_plan(selection: Selection) -> list[Invocation]:
    """Prefer named integration targets and explicit unit filters, otherwise run the crate."""
    if selection.full:
        return [RUST_FULL_SUITE]
    explicit, root = selection.targets, selection.scope.root
    filters = {Path(path).stem for path in explicit if not path.startswith("tests/")}
    test_paths = {path for path in explicit if path.startswith("tests/")}
    for path in selection.scope.changed:
        if not path.endswith(".rs"):
            continue
        stem = Path(path).stem
        if path.startswith("tests/") or (path.startswith("src/") and (root / "tests" / f"{stem}.rs").is_file()):
            test_paths.add(path if path.startswith("tests/") else f"tests/{stem}.rs")
    targets = {rust_test_target(root, path) for path in test_paths}
    if "" in targets:
        return [RUST_FULL_SUITE]
    invocations = [
        Invocation("rust", f"unit filter {stem}", ("cargo", "test", stem, "--quiet")) for stem in sorted(filters)
    ]
    invocations += [
        Invocation("rust", f"integration target {stem}", ("cargo", "test", "--test", stem, "--quiet"))
        for stem in sorted(targets)
    ]
    return invocations or [RUST_FULL_SUITE]


def rust_test_target(root: Path, filename: str) -> str:
    """Resolve an integration test file to its declared or auto-discovered Cargo target."""
    try:
        manifest = tomllib.loads((root / "Cargo.toml").read_text())
    except OSError, tomllib.TOMLDecodeError:
        return ""
    path = Path(filename)
    entries = [entry for entry in manifest.get("test", []) if "path" in entry and "name" in entry]
    for entry in sorted(entries, key=lambda entry: len(Path(entry["path"]).parent.parts), reverse=True):
        declared = Path(entry["path"])
        if path == declared or (
            declared.parent != Path("tests")
            and declared.parent.is_relative_to("tests")
            and path.is_relative_to(declared.parent)
        ):
            return entry["name"]
    if len(path.parts) > 2 and (root / "tests" / path.parts[1] / "main.rs").is_file():
        return path.parts[1]
    return path.stem if len(path.parts) == 2 else ""


def javascript_plan(selection: Selection) -> list[Invocation]:
    """Keep dependency-aware Vitest selection in addition to explicit test targets."""
    root = selection.scope.root
    package = json.loads((root / "package.json").read_text())
    manager = package_manager(root, package)
    test_script = (package.get("scripts") or {}).get("test", "")
    runner = javascript_runner(package, test_script)
    if not runner:
        return script_plan(selection, manager, test_script)
    arguments = ("node", "--test") if runner == "node" else (*RUNNER_PREFIXES.get(manager, ("false",)), runner)
    if runner == "vitest":
        return vitest_plan(selection, arguments)
    if selection.full:
        return [Invocation(runner, "full suite", arguments)]
    targets = selection.targets
    scope = f"{len(targets)} related tests" if targets else "full suite"
    return [Invocation(runner, scope, (*arguments, *sorted(targets)))]


def package_manager(root: Path, package: dict) -> str:
    """Prefer the declared package manager, then the lockfile present, then npm."""
    manager = package.get("packageManager", "").split("@", 1)[0]
    if manager:
        return manager
    return next((name for lock, name in LOCKFILE_MANAGERS if (root / lock).is_file()), "npm")


def javascript_runner(package: dict, test_script: str) -> str:
    """Name the JavaScript test runner the project depends on, or an empty string when none is known."""
    dependencies = dict(package.get("dependencies") or {}, **(package.get("devDependencies") or {}))
    runner = next((name for name in ("vitest", "jest") if dependencies.get(name) is not None), "")
    if not runner and re.search(r"(^|\s)node\s+--test(\s|$)", test_script):
        return "node"
    return runner


def script_plan(selection: Selection, manager: str, test_script: str) -> list[Invocation]:
    """Fall back to the package's test script when no known runner is installed."""
    if test_script:
        arguments = (manager, "run", "test") if manager == "bun" else (manager, "test")
        return [Invocation(f"{manager} test", "full suite", arguments)]
    if selection.targets or changed_language(selection.scope.rule, selection.scope.changed):
        raise UnknownTestCommand("test command could not be determined")
    # A dependency or lockfile bump in a project that declares no JavaScript tests has nothing to run.
    return []


def vitest_plan(selection: Selection, arguments: tuple[str, ...]) -> list[Invocation]:
    """Run named tests plus Vitest's dependency-aware selection for changed sources."""
    if selection.triggered:
        return [Invocation("vitest", "full suite", (*arguments, "run"))]
    targets, root = selection.targets, selection.scope.root
    invocations: list[Invocation] = []
    if targets:
        invocations.append(
            Invocation("vitest", f"{len(targets)} related tests", (*arguments, "run", *sorted(targets)))
        )
    sources = sorted(
        path
        for path in selection.scope.changed
        if Path(path).suffix in {".js", ".jsx", ".ts", ".tsx"}
        and not is_test(selection.scope.rule, path)
        and (root / path).is_file()
    )
    if sources:
        invocations.append(
            Invocation(
                "vitest",
                f"{len(sources)} changed files",
                (*arguments, "related", "--run", "--passWithNoTests", *sources),
            )
        )
    return invocations or [Invocation("vitest", "full suite", (*arguments, "run"))]
