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


@pytest.mark.parametrize(
    "language,template",
    [
        ("python", "furedea/template-python"),
        ("typescript", "furedea/template-typescript"),
        ("rust", "furedea/template-rust"),
        ("go", "furedea/template-go"),
        ("tex", "furedea/template-tex"),
        ("minimal", "furedea/template-minimal"),
    ],
)
@pytest.mark.parametrize("spelling", ["separate", "equals"])
def test_language_expands_to_its_template(language: str, template: str, spelling: str) -> None:
    given = ["--lang", language] if spelling == "separate" else [f"--lang={language}"]
    expanded = repo.expand_language(["--private", *given, "--description", "d"])
    assert expanded == ["--private", "--description", "d", "--template", template]
    assert repo.create_options(expanded)


def test_options_without_language_are_unchanged() -> None:
    options = ["--private", "--template", "owner/template"]
    assert repo.expand_language(options) == options


@pytest.mark.parametrize(
    "extra", [["--template", "owner/t"], ["--template=owner/t"], ["-p", "owner/t"], ["-p=owner/t"]]
)
def test_language_and_template_are_mutually_exclusive(extra: list[str]) -> None:
    with pytest.raises(ValueError, match=r"--lang and --template/-p are mutually exclusive"):
        repo.expand_language(["--private", "--lang", "rust", *extra])


@pytest.mark.parametrize("given", [["--lang", "cobol"], ["--lang=cobol"], ["--lang"], ["--lang="]])
def test_unknown_language_lists_supported_values(given: list[str]) -> None:
    with pytest.raises(ValueError, match="unsupported language") as error:
        repo.expand_language(["--private", *given])
    assert all(language in str(error.value) for language in repo.LANGUAGE_TEMPLATES)


def test_template_rename_preserves_unrelated_manifest_fields(tmp_path: Path) -> None:
    manifest = tmp_path / "Cargo.toml"
    manifest.write_text('[package]\nname = "template-rust"\nversion = "0.1.0"\n')
    package = tmp_path / "package.json"
    package.write_text('{"name":"template-node","private":true}')
    repo.apply_template(tmp_path, "owner/new-project")
    assert manifest.read_text() == '[package]\nname = "new-project"\nversion = "0.1.0"\n'
    assert json.loads(package.read_text()) == {"name": "new-project", "private": True}


def test_template_rename_rewrites_go_module_path_only(tmp_path: Path) -> None:
    manifest = tmp_path / "go.mod"
    manifest.write_text("module github.com/furedea/template-go\n\ngo 1.24\n\nrequire example.com/dep v1.0.0\n")
    source = tmp_path / "main.go"
    source.write_text('package main\n\nimport _ "example.com/dep"\n')
    repo.apply_template(tmp_path, "someone/new-project")
    assert manifest.read_text() == (
        "module github.com/someone/new-project\n\ngo 1.24\n\nrequire example.com/dep v1.0.0\n"
    )
    assert source.read_text() == 'package main\n\nimport _ "example.com/dep"\n'
