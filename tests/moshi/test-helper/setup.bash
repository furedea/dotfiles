REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

function create_moshi_hook_stub() {
  /bin/cat >|"$MOSHI_HOOK_STUB" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"

readonly ATTEMPT_FILE="${MOSHI_ATTEMPT_FILE:?}"
readonly ARGS_FILE="${MOSHI_ARGS_FILE:?}"
readonly EVENTS_FILE="${MOSHI_EVENTS_FILE:?}"

printf '%s\n' "$*" >>"$ARGS_FILE"
printf 'moshi:%s\n' "$*" >>"$EVENTS_FILE"

case "${1:-}" in
  status)
    attempt=0
    if [[ -f "$ATTEMPT_FILE" ]]; then
      read -r attempt <"$ATTEMPT_FILE"
    fi
    attempt=$((attempt + 1))
    printf '%s\n' "$attempt" >|"$ATTEMPT_FILE"

    if ((attempt <= ${MOSHI_STATUS_FAILURES:-0})); then
      printf '%s\n' '{"paired":false,"secretStore":"keychain"}'
    else
      printf '%s\n' '{"paired":true,"secretStore":"keychain"}'
    fi
    ;;
  serve)
    ;;
  *)
    exit 2
    ;;
esac
EOF
  chmod 0700 "$MOSHI_HOOK_STUB"
}
