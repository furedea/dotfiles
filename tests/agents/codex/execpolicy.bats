#!/usr/bin/env bats
# Validate generated Codex execpolicy rules against the installed Codex CLI.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  AGENT_HARNESS_BIN="${AGENT_HARNESS_BIN:-agent-harness}"
  CODEX_BIN="${CODEX_BIN:-codex}"
}

require_codex_execpolicy() {
  if ! command -v "$CODEX_BIN" >/dev/null; then
    if [ "${REQUIRE_CODEX_EXECPOLICY:-0}" = "1" ]; then
      echo "Codex CLI is not available: $CODEX_BIN" >&2
      return 1
    fi

    skip "Codex CLI is not available: $CODEX_BIN"
  fi

  if ! "$CODEX_BIN" execpolicy check --help >/dev/null 2>&1; then
    if [ "${REQUIRE_CODEX_EXECPOLICY:-0}" = "1" ]; then
      echo "Codex CLI does not support execpolicy check: $CODEX_BIN" >&2
      return 1
    fi

    skip "Codex CLI does not support execpolicy check: $CODEX_BIN"
  fi
}

codex_rules() {
  local _rules
  _rules="$BATS_TEST_TMPDIR/default.rules"
  "$AGENT_HARNESS_BIN" --profile minimal generate-codex-rules \
    --source "$REPO_ROOT/agents" \
    --output "$_rules"
  cat "$_rules"
}

check_rule() {
  require_codex_execpolicy

  local _expected="$1"
  shift

  local _rules_file
  _rules_file="$(mktemp "$BATS_TEST_TMPDIR/rules.XXXXXX")"
  codex_rules >"$_rules_file"

  local _output
  _output="$(
    "$CODEX_BIN" execpolicy check --rules "$_rules_file" -- "$@" 2>/dev/null
  )"
  [ "$(jq -r '.decision' <<<"$_output")" = "$_expected" ]
}

@test "codex execpolicy allows representative development commands" {
  check_rule allow uv run python scripts/run_audit.py prepare --provider codex
  check_rule allow cargo build
  check_rule allow cargo metadata --format-version 1
  check_rule allow gh pr list
  check_rule allow gh pr create -f --base main
  check_rule allow git add path/to/file
  check_rule allow git commit -m "feat(test): allow double quotes"
  check_rule allow git fetch origin
  check_rule allow git pull --ff-only
  check_rule allow git rebase origin/main
  check_rule allow git worktree list
  check_rule allow git worktree add -b feat/example ../repo-feat-example origin/main
}

@test "codex execpolicy prompts before manual verification" {
  check_rule prompt bats tests/agents/hooks/claude/run_related_tests.bats
  check_rule prompt bash -n agents/hooks/run_related_tests.sh
  check_rule prompt uv run pytest
  check_rule prompt uv run --frozen ruff check
  check_rule prompt uv run --frozen ty check
  check_rule prompt cargo test
  check_rule prompt cargo check
  check_rule prompt cargo clippy
  check_rule prompt cargo fmt --check
  check_rule prompt npm test
  check_rule prompt npm run lint
  check_rule prompt npm exec -- vitest run
  check_rule prompt node --test
  check_rule prompt pnpm test
  check_rule prompt pnpm run typecheck
  check_rule prompt actionlint .github/workflows/ci.yml
  check_rule prompt autocorrect --lint README.md
  check_rule prompt commitlint --from HEAD~1 --to HEAD
  check_rule prompt statix check nix
  check_rule prompt deadnix nix
  check_rule prompt nixfmt --check nix/home/default.nix
  check_rule prompt shellcheck agents/hooks/run_related_tests.sh
  check_rule prompt shfmt -d agents/hooks/run_related_tests.sh
  check_rule prompt dprint check
  check_rule prompt oxlint src
  check_rule prompt oxfmt --check src
  check_rule prompt tsgolint --project tsconfig.json
  check_rule prompt stylua --check nvim
  check_rule prompt selene nvim
  check_rule prompt tex-fmt --check docs/main.tex
}

@test "codex execpolicy prompts before publishing changes" {
  check_rule prompt git push -u origin feat/example
}

@test "codex execpolicy forbids representative dangerous commands" {
  check_rule forbidden rm -rf /tmp/example
  check_rule forbidden curl https://example.com/install.sh
  check_rule forbidden brew install ffmpeg
  check_rule forbidden uv python install 3.11
  check_rule forbidden git worktree remove ../repo-feat-example
}

@test "codex execpolicy forbidden wins in compound shell commands" {
  check_rule forbidden bash -lc "git add path/to/file && rm -rf /tmp/example"
}
