#!/usr/bin/env bats
# Git signing restores only the current user's macOS agent when needed.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/scripts/git/sign_ssh.sh"
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  export AGENT_SOCKET="$BATS_TEST_TMPDIR/Listeners"
  export DISCOVERY_LOG="$BATS_TEST_TMPDIR/discovery"
  export EXPECTED_UID="$(id -u)"
  unset SSH_AUTH_SOCK
  /usr/bin/perl -MIO::Socket::UNIX -e 'IO::Socket::UNIX->new(Local => $ARGV[0], Listen => 1) or die $!' "$AGENT_SOCKET"
  cat > "$BATS_TEST_TMPDIR/bin/launchctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$DISCOVERY_LOG"
[[ "${DISCOVERY_FAILED:-0}" == 0 ]] || exit 1
printf 'path = /System/Library/LaunchAgents/com.openssh.ssh-agent.plist\n'
printf 'path = %s\n' "$AGENT_SOCKET"
EOF
  cat > "$BATS_TEST_TMPDIR/bin/stat" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${SOCKET_UID:-$EXPECTED_UID}"
EOF
  cat > "$BATS_TEST_TMPDIR/bin/ssh-keygen" <<'EOF'
#!/usr/bin/env bash
printf 'socket=%s\n' "${SSH_AUTH_SOCK:-unset}"
printf 'arg=%s\n' "$@"
exit "${SIGN_EXIT:-0}"
EOF
  chmod +x "$BATS_TEST_TMPDIR/bin/"*
}

@test "signing discovers the current user's agent and preserves arguments" {
  run bash "$SCRIPT" -Y sign -n git -f "public identity.pub"
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=$AGENT_SOCKET"$'\n'* ]]
  [[ "$output" == *"arg=public identity.pub" ]]
  [ "$(cat "$DISCOVERY_LOG")" = "print gui/$EXPECTED_UID/com.openssh.ssh-agent" ]
}

@test "an explicitly configured agent is preserved without discovery" {
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/forwarded-agent"
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=$SSH_AUTH_SOCK"$'\n'* ]]
  [ ! -e "$DISCOVERY_LOG" ]
}

@test "verification does not discover or attach an agent" {
  run bash "$SCRIPT" -Y verify
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=unset"$'\n'* ]]
  [ ! -e "$DISCOVERY_LOG" ]
}

@test "discovery failure leaves the original signer behavior intact" {
  export DISCOVERY_FAILED=1 SIGN_EXIT=23
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 23 ]
  [[ "$output" == "socket=unset"$'\n'* ]]
}

@test "a socket owned by another user is not attached" {
  export SOCKET_UID="$((EXPECTED_UID + 1))"
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=unset"$'\n'* ]]
}

@test "a regular file cannot substitute for the agent socket" {
  rm "$AGENT_SOCKET"
  touch "$AGENT_SOCKET"
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=unset"$'\n'* ]]
}
