#!/usr/bin/env bats
# Validate provider-specific Agent Skills rendering from common sources.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  PYTHON="$(nix build --no-link --print-out-paths "$REPO_ROOT#python3")/bin/python"
}

render_skills() {
  local overrides_json
  overrides_json="$BATS_TEST_TMPDIR/overrides.json"
  nix eval --json "$REPO_ROOT#lib.agentSkillOverrides" >"$overrides_json"

  "$PYTHON" "$REPO_ROOT/agents/scripts/render_skills.py" \
    --source "$REPO_ROOT/agents/skills" \
    --overrides "$overrides_json" \
    --output "$BATS_TEST_TMPDIR/rendered"
}

@test "source skill frontmatter contains only common Agent Skills fields" {
  "$PYTHON" - "$REPO_ROOT/agents/skills" <<'PY'
import pathlib
import re
import sys

common = {"name", "description"}
root = pathlib.Path(sys.argv[1])
bad = []

for path in sorted(root.glob("*/SKILL.md")):
    text = path.read_text()
    frontmatter = text.split("---\n", 2)[1]
    keys = re.findall(r"^([A-Za-z0-9_-]+):", frontmatter, flags=re.MULTILINE)
    extra = sorted(set(keys) - common)
    if extra:
        bad.append(f"{path}: {', '.join(extra)}")

if bad:
    raise SystemExit("\n".join(bad))
PY
}

@test "renderer adds provider-specific skill frontmatter" {
  render_skills

  grep -q 'argument-hint: "{direct | pr-per-feature}"' \
    "$BATS_TEST_TMPDIR/rendered/claude/skills/git-commit-split/SKILL.md"
  grep -q 'argument-hint: "{direct | pr-per-feature}"' \
    "$BATS_TEST_TMPDIR/rendered/codex/skills/git-commit-split/SKILL.md"
  grep -q 'disable-model-invocation: true' \
    "$BATS_TEST_TMPDIR/rendered/claude/skills/skill-auditor/SKILL.md"
  grep -q 'allowed-tools: \["Bash", "Read", "Glob"\]' \
    "$BATS_TEST_TMPDIR/rendered/claude/skills/report-doc-conflict/SKILL.md"
  ! grep -q 'allowed-tools:' \
    "$BATS_TEST_TMPDIR/rendered/codex/skills/report-doc-conflict/SKILL.md"
}

@test "home-manager uses rendered provider skill directories" {
  grep -q 'renderedAgentSkills = pkgs.runCommand "agent-skills"' "$REPO_ROOT/nix/home/default.nix"
  grep -q '".codex/skills".source = "${renderedAgentSkills}/codex/skills";' "$REPO_ROOT/nix/home/default.nix"
  grep -q '".claude/skills".source = "${renderedAgentSkills}/claude/skills";' "$REPO_ROOT/nix/home/default.nix"
}
