"""Select project quality tools without executing them."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import tomllib


PYTHON_FORMATTER_NAMES = frozenset({"black", "autopep8", "blue", "yapf"})
HOOK_MANIFEST_NAMES = ("lefthook.yml", "lefthook.yaml", ".pre-commit-config.yaml")
DPRINT_CONFIG_NAMES = ("dprint.json", "dprint.jsonc", ".dprint.json", ".dprint.jsonc")
OTHER_FORMATTER_CONFIG_NAMES = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    "prettier.config.js",
    "prettier.config.cjs",
    "biome.json",
    "biome.jsonc",
)
OXFMT_CONFIG_NAMES = (".oxfmtrc", ".oxfmtrc.json", ".oxfmtrc.jsonc")
JS_FORMATTER_PACKAGES = {"prettier": "prettier", "@biomejs/biome": "biome", "oxfmt": "oxfmt"}


@dataclass(frozen=True, slots=True)
class Step:
    """One quality command, including its working directory and output semantics."""

    label: str
    arguments: tuple[str, ...]
    cwd: Path | None = None
    writes_stdout: bool = False
    reports_warnings: bool = False
    policy_error: str | None = None
    note: str | None = None
    mutates: bool = False


def project_root(start: Path, markers: tuple[str, ...]) -> Path | None:
    """Find the nearest ancestor containing one of the project markers."""
    return next(
        (
            directory
            for directory in (start, *start.parents)
            if any((directory / marker).is_file() for marker in markers)
        ),
        None,
    )


def project_files(start: Path, names: tuple[str, ...]) -> tuple[Path, ...]:
    """Return formatter declarations from the nearest ancestor that has any."""
    for directory in (start, *start.parents):
        found = tuple(directory / name for name in names if (directory / name).is_file())
        if found:
            return found
    return ()


def toml_data(path: Path) -> dict | None:
    """Read a project TOML file without turning malformed configuration into a fallback."""
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except OSError, tomllib.TOMLDecodeError:
        return None
    return value if isinstance(value, dict) else {}


def json_data(path: Path) -> dict | None:
    """Read a project JSON file without turning malformed configuration into a fallback."""
    try:
        value = json.loads(path.read_text(errors="replace"))
    except OSError, json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else {}


def dependency_names(data: dict) -> set[str]:
    """Collect normalized dependency names from common PEP 621 and uv tables."""
    values: list[object] = []
    project = data.get("project")
    if isinstance(project, dict):
        values.append(project.get("dependencies"))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            values.extend(optional.values())
    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        values.extend(groups.values())
    names: set[str] = set()
    for group in values:
        if isinstance(group, list):
            for requirement in group:
                if isinstance(requirement, str):
                    names.add(re.split(r"[<=>!~\[]", requirement, maxsplit=1)[0].strip().lower().replace("-", "_"))
    return names


def hook_command_text(root: Path) -> str:
    """Read static hook manifests that declare the project's quality commands."""
    parts = []
    for name in HOOK_MANIFEST_NAMES:
        path = root / name
        if path.is_file():
            parts.append(path.read_text(errors="replace"))
    return "\n".join(parts)


def python_tools(root: Path) -> tuple[frozenset[str], str | None, str | None]:
    """Return (formatter names, linter name, blocking error) declared by a Python project.

    `[tool.ruff]` or a ruff dependency adopts the linter only; the formatter is
    adopted by `[tool.ruff.format]` or a static `ruff format` hook command.
    """
    formatters: set[str] = set()
    linter: str | None = None
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = toml_data(pyproject)
        if data is None:
            return frozenset(), None, "invalid pyproject.toml"
        tools_value = data.get("tool")
        tools: dict = dict(tools_value) if isinstance(tools_value, dict) else {}
        dependencies = dependency_names(data)
        if "ruff" in tools or "ruff" in dependencies:
            linter = "ruff"
        if isinstance(tools.get("ruff"), dict) and isinstance(tools["ruff"].get("format"), dict):
            formatters.add("ruff")
        formatters.update(name for name in PYTHON_FORMATTER_NAMES if name in tools or name in dependencies)
    lock = root / "uv.lock"
    if lock.is_file() and 'name = "ruff"' in lock.read_text(errors="replace"):
        linter = linter or "ruff"
    commands = hook_command_text(root)
    if re.search(r"\bruff[ -]format\b", commands):
        formatters.add("ruff")
    if re.search(r"\bruff[ -]check\b", commands):
        linter = linter or "ruff"
    if re.search(r"\bblack\b", commands):
        formatters.add("black")
    return frozenset(formatters), linter, None


def js_dependency_names(data: dict) -> set[str]:
    """Collect package names a JavaScript project declares statically."""
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        group = data.get(key)
        if isinstance(group, dict):
            names.update(name for name in group if isinstance(name, str))
    return names


def js_config_tool(name: str) -> str:
    if name.startswith("biome"):
        return "biome"
    if name.startswith(".oxfmtrc"):
        return "oxfmt"
    return "prettier"


def javascript_formatters(start: Path, root: Path | None) -> tuple[frozenset[str], str | None]:
    """Return (formatter names, blocking error) declared by a JS/TS project."""
    formatters: set[str] = set()
    if root is not None:
        data = json_data(root / "package.json")
        if data is None:
            return frozenset(), "invalid package.json"
        dependencies = js_dependency_names(data)
        formatters.update(tool for package, tool in JS_FORMATTER_PACKAGES.items() if package in dependencies)
        if data.get("prettier") is not None:
            formatters.add("prettier")
    for config in project_files(start, OTHER_FORMATTER_CONFIG_NAMES + OXFMT_CONFIG_NAMES):
        formatters.add(js_config_tool(config.name))
    return frozenset(formatters), None


def policy_step(path: Path, reason: str, cwd: Path | None = None) -> Step:
    """Represent a project selection decision that must be shown instead of silently skipped."""
    return Step("formatter selection", (), cwd, policy_error=f"{reason} Personal defaults were not used for {path}.")


def note_step(reason: str, cwd: Path | None = None) -> Step:
    """Report a skipped mutation while leaving independently adopted checks running."""
    return Step("formatter selection", (), cwd, note=reason)


def python_plan(path: Path) -> tuple[Step, ...]:
    """Order adopted Python tools as fix, then format, then a final lint."""
    filename = str(path)
    lint_tail = ("check", "--output-format=concise", "--quiet", filename)
    root = project_root(path.parent, ("pyproject.toml", "uv.lock"))
    if root is None:
        return (
            note_step("No formatter declaration; formatting and fixes were skipped."),
            Step("ruff lint", ("ruff", *lint_tail)),
        )
    formatters, linter, error = python_tools(root)
    if error:
        return (policy_step(path, f"Project {root.name} has {error}", root),)
    prefix = ("uv", "run", "--frozen") if (root / "uv.lock").is_file() else ()
    lint_command = (*prefix, "ruff") if linter == "ruff" else ("ruff",)
    steps: list[Step] = []
    if len(formatters) > 1:
        steps.append(
            note_step(
                f"Conflicting formatters ({', '.join(sorted(formatters))}); formatting and fixes were skipped.",
                root,
            )
        )
    elif not formatters:
        steps.append(note_step(f"No formatter declaration in {root.name}; formatting and fixes were skipped.", root))
    elif (formatter := next(iter(formatters))) == "ruff":
        steps += [
            Step("ruff fix", (*prefix, "ruff", "check", "--fix-only", "--quiet", filename), root, mutates=True),
            Step("ruff format", (*prefix, "ruff", "format", filename), root, mutates=True),
        ]
    elif formatter == "black":
        if linter == "ruff":
            steps.append(
                Step(
                    "ruff fix",
                    (*prefix, "ruff", "check", "--fix-only", "--quiet", filename),
                    root,
                    mutates=True,
                )
            )
        steps.append(Step("black format", (*prefix, "black", filename), root, mutates=True))
    else:
        steps.append(
            note_step(
                f"Unsupported formatter {formatter} adopted by {root.name}; formatting and fixes were skipped.",
                root,
            )
        )
    steps.append(Step("ruff lint", (*lint_command, *lint_tail), root))
    return tuple(steps)


def javascript_plan(path: Path) -> tuple[Step, ...]:
    """Apply oxfmt only when the project adopts it; keep oxlint checks either way."""
    filename = str(path)
    root = project_root(path.parent, ("package.json",))
    formatters, error = javascript_formatters(path.parent, root)
    if error:
        return (policy_step(path, f"Project {root.name if root else path.parent.name} has {error}", root),)
    lint = (Step("oxlint lint", ("oxlint", "--deny-warnings", filename)),)
    if len(formatters) > 1:
        return (
            note_step(f"Conflicting formatters ({', '.join(sorted(formatters))}); formatting and fixes were skipped."),
            *lint,
        )
    if not formatters:
        return (note_step("No formatter declaration; formatting and fixes were skipped."), *lint)
    if (formatter := next(iter(formatters))) != "oxfmt":
        return (
            note_step(f"Unsupported formatter {formatter}; formatting and fixes were skipped."),
            *lint,
        )
    return (
        Step("oxlint fix", ("oxlint", "--fix", filename), mutates=True),
        Step("oxfmt format", ("oxfmt", "--write", filename), mutates=True),
        Step("oxlint lint", ("oxlint", "--deny-warnings", filename)),
    )


def plan(kind: str, path: Path, *, readonly: bool = False) -> tuple[Step, ...]:
    """Choose the existing quality tools without running any of them."""
    steps = _plan(kind, path)
    if readonly:
        steps = tuple(step for step in steps if not step.mutates)
    return steps


def _plan(kind: str, path: Path) -> tuple[Step, ...]:
    filename = str(path)
    if kind == "py":
        return python_plan(path)
    if kind == "js":
        return javascript_plan(path)
    if kind == "json_toml":
        declarations = project_files(path.parent, DPRINT_CONFIG_NAMES + OTHER_FORMATTER_CONFIG_NAMES)
        dprint = tuple(item for item in declarations if item.name in DPRINT_CONFIG_NAMES)
        alternatives = tuple(item for item in declarations if item.name in OTHER_FORMATTER_CONFIG_NAMES)
        if alternatives:
            names = ", ".join(item.name for item in alternatives)
            reason = (
                f"Project formatter declarations {names} conflict with dprint."
                if dprint
                else f"Project formatter declaration {names} takes precedence over dprint."
            )
            return (policy_step(path, reason),)
        project_config = dprint[0] if dprint else None
        config = project_config or Path.home() / "dprint.json"
        root = project_config.parent if project_config else path.parent
        relative = str(path.relative_to(root)) if project_config else path.name
        arguments = (
            "--config",
            str(config),
            "--includes-override",
            relative,
            "--allow-no-files",
        )
        return (
            Step("dprint format", ("dprint", "fmt", *arguments), root, mutates=True),
            Step("dprint lint", ("dprint", "check", *arguments), root),
        )
    if kind == "lua":
        root = project_root(path.parent, ("selene.toml",)) or path.parent
        return (
            Step("stylua format", ("stylua", filename), mutates=True),
            Step("selene lint", ("selene", filename), root),
        )
    if kind == "tex":
        steps = (Step("tex-fmt format", ("tex-fmt", filename), mutates=True),)
        if path.suffix != ".bib":
            steps += (Step("chktex lint", ("chktex", "-q", "-n22", "-n30", filename), reports_warnings=True),)
        return steps
    if kind == "md":
        return (
            Step("autocorrect format", ("autocorrect", "--fix", filename), mutates=True),
            Step("prettierd format", ("prettierd", filename), writes_stdout=True, mutates=True),
        )
    if kind == "gha":
        if ".github/workflows/" not in filename or path.suffix not in {".yml", ".yaml"}:
            return ()
        return (Step("actionlint lint", ("actionlint", "-oneline", filename)),)
    commands: dict[str, tuple[tuple, ...]] = {
        "rs": (("rustfmt format", True, "rustfmt"),),
        "txt": (("autocorrect format", True, "autocorrect", "--fix"),),
        "sh": (
            ("shfmt format", True, "shfmt", "-w"),
            ("shellcheck lint", False, "shellcheck", "-x", "-P", "SCRIPTDIR"),
        ),
        "nix": (
            ("nixfmt format", True, "nixfmt"),
            ("statix fix", True, "statix", "fix"),
            ("statix lint", False, "statix", "check"),
            ("deadnix lint", False, "deadnix", "--fail"),
        ),
    }
    if kind not in commands:
        raise ValueError(f"Unknown quality language: {kind}")
    return tuple(Step(label, (*arguments, filename), mutates=mutates) for label, mutates, *arguments in commands[kind])
