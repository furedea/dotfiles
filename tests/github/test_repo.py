"""The public repository workflow's input and template contracts."""

import json
from pathlib import Path

import pytest

from tests.runtime import load_script_module


repo = load_script_module("github/repo.py", "repo")


@pytest.mark.parametrize("visibility", ["--public", "--private", "--internal"])
def test_exactly_one_visibility_is_accepted(visibility: str) -> None:
    assert not repo.create_options([visibility])


@pytest.mark.parametrize("arguments", [[], ["--public", "--private"], ["--public", "--public"]])
def test_missing_or_ambiguous_visibility_is_rejected(arguments: list[str]) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        repo.create_options(arguments)


@pytest.mark.parametrize("option", ["--clone", "-c", "--source=.", "-s=.", "--push", "--remote=origin", "-r=origin"])
def test_local_clone_control_cannot_be_overridden(option: str) -> None:
    with pytest.raises(ValueError, match="local clone destination"):
        repo.create_options(["--private", option])


@pytest.mark.parametrize(
    "arguments", [["--template", "owner/template"], ["--template=owner/template"], ["-p", "owner/template"]]
)
def test_template_selection_requires_waiting_for_remote_readiness(arguments: list[str]) -> None:
    assert repo.create_options(["--private", *arguments])


def test_template_rename_preserves_unrelated_manifest_fields(tmp_path: Path) -> None:
    manifest = tmp_path / "Cargo.toml"
    manifest.write_text('[package]\nname = "template-rust"\nversion = "0.1.0"\n')
    package = tmp_path / "package.json"
    package.write_text('{"name":"template-node","private":true}')
    repo.apply_template(tmp_path, "new-project")
    assert manifest.read_text() == '[package]\nname = "new-project"\nversion = "0.1.0"\n'
    assert json.loads(package.read_text()) == {"name": "new-project", "private": True}
