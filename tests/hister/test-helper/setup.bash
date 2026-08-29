REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

function create_security_stub() {
  /bin/cat >|"$SECURITY_STUB" <<'EOF'
#!/usr/bin/env bash
set -euxCo pipefail
cd "$(dirname "$0")"

readonly ARGS_FILE="${HISTER_SECURITY_ARGS_FILE:?}"

printf '%s\n' "$*" >|"$ARGS_FILE"
if [[ "${HISTER_SECURITY_UNAVAILABLE:-false}" == "true" ]]; then
  exit 44
fi

set +x
if [[ "${HISTER_SECURITY_EMPTY:-false}" == "true" ]]; then
  printf '\n'
  exit 0
fi
printf '%s\n' 'test-hister-credential'
EOF
  chmod 0700 "$SECURITY_STUB"
}

function create_hister_stub() {
  /bin/cat >|"$HISTER_STUB" <<'EOF'
#!/usr/bin/env bash
set -euxCo pipefail
cd "$(dirname "$0")"

readonly EVENTS_FILE="${HISTER_EVENTS_FILE:?}"

set +x
[[ "${HISTER__APP__ACCESS_TOKEN:-}" == 'test-hister-credential' ]]
printf '%s\n' "$*" >|"$EVENTS_FILE"
EOF
  chmod 0700 "$HISTER_STUB"
}
