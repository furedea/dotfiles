REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

# The stub stands in for the real agy and prints each argument it receives on its own line.
function create_agy_stub() {
  /bin/cat >|"$AGY_STUB" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@"
EOS
  chmod 0700 "$AGY_STUB"
}
