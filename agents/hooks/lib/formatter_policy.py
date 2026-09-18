"""Select project quality tools without executing them."""

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


PYTHON_TOOL_NAMES = frozenset({"black", "autopep8", "blue", "yapf"})
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


@dataclass(frozen=True, slots=True)
class Step:
    """One quality command, including its working directory and output semantics."""

    label: str
    arguments: tuple[str, ...]
    cwd: Path | None = None
    writes_stdout: bool = False
    reports_warnings: bool = False
    policy_error: str | None = None


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


def python_project_tool(root: Path) -> str | None:
    """Return the declared Python formatter, or None when the project is ambiguous."""
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = toml_data(pyproject)
        if data is None:
            return "invalid pyproject.toml"
        tools_value = data.get("tool")
        tools: dict[str, object] = dict(tools_value) if isinstance(tools_value, dict) else {}
        dependencies = dependency_names(data)
        alternatives = sorted(name for name in PYTHON_TOOL_NAMES if name in tools)
        has_ruff = "ruff" in tools or "ruff" in dependencies
        if has_ruff and alternatives:
            return f"multiple formatters ({', '.join(['ruff', *alternatives])})"
        if has_ruff:
            return "ruff"
        if alternatives:
            return alternatives[0]
    lock = root / "uv.lock"
    if lock.is_file() and 'name = "ruff"' in lock.read_text(errors="replace"):
        return "ruff"
    return None


def policy_step(path: Path, reason: str, cwd: Path | None = None) -> Step:
    """Represent a project selection decision that must be shown instead of silently skipped."""
    return Step("formatter selection", (), cwd, policy_error=f"{reason} Personal defaults were not used for {path}.")


def plan(kind: str, path: Path) -> tuple[Step, ...]:
    """Choose the existing quality tools without running any of them."""
    filename = str(path)
    if kind == "py":
        root = project_root(path.parent, ("pyproject.toml", "uv.lock"))
        if root:
            tool = python_project_tool(root)
            if tool != "ruff":
                declared = tool or "an unknown formatter"
                return (
                    policy_step(
                        path,
                        f"Project {root.name} declares {declared}; automatic ruff selection is unsafe.",
                        root,
                    ),
                )
        prefix = ("uv", "run", "--frozen", "ruff") if root else ("ruff",)
        return (
            Step("ruff format", (*prefix, "format", filename), root),
            Step("ruff fix", (*prefix, "check", "--fix-only", "--quiet", filename), root),
            Step("ruff lint", (*prefix, "check", "--output-format=concise", "--quiet", filename), root),
        )
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
            Step("dprint format", ("dprint", "fmt", *arguments), root),
            Step("dprint lint", ("dprint", "check", *arguments), root),
        )
    if kind == "lua":
        root = project_root(path.parent, ("selene.toml",)) or path.parent
        return (Step("stylua format", ("stylua", filename)), Step("selene lint", ("selene", filename), root))
    if kind == "tex":
        steps = (Step("tex-fmt format", ("tex-fmt", filename)),)
        if path.suffix != ".bib":
            steps += (Step("chktex lint", ("chktex", "-q", "-n22", "-n30", filename), reports_warnings=True),)
        return steps
    if kind == "md":
        return (
            Step("autocorrect format", ("autocorrect", "--fix", filename)),
            Step("prettierd format", ("prettierd", filename), writes_stdout=True),
        )
    if kind == "gha":
        if ".github/workflows/" not in filename or path.suffix not in {".yml", ".yaml"}:
            return ()
        return (Step("actionlint lint", ("actionlint", "-oneline", filename)),)
    commands = {
        "rs": (("rustfmt format", "rustfmt"),),
        "txt": (("autocorrect format", "autocorrect", "--fix"),),
        "sh": (("shfmt format", "shfmt", "-w"), ("shellcheck lint", "shellcheck", "-x", "-P", "SCRIPTDIR")),
        "js": (
            ("oxfmt format", "oxfmt", "--write"),
            ("oxlint fix", "oxlint", "--fix"),
            ("oxlint lint", "oxlint", "--deny-warnings"),
        ),
        "nix": (
            ("nixfmt format", "nixfmt"),
            ("statix fix", "statix", "fix"),
            ("statix lint", "statix", "check"),
            ("deadnix lint", "deadnix", "--fail"),
        ),
    }
    if kind not in commands:
        raise ValueError(f"Unknown quality language: {kind}")
    return tuple(Step(label, (*arguments, filename)) for label, *arguments in commands[kind])
