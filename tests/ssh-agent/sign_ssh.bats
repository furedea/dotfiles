#!/usr/bin/env bats
# Git signing attaches only the current user's 1Password agent when signing.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/scripts/git/sign_ssh.sh"
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  export HOME="$BATS_TEST_TMPDIR/home"
  export AGENT_DIR="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t"
  export AGENT_SOCKET="$AGENT_DIR/agent.sock"
  export EXPECTED_UID="$(id -u)"
  unset SSH_AUTH_SOCK
  mkdir -p "$AGENT_DIR"
  # The full path exceeds the sockaddr_un limit, so bind by a relative name.
  /usr/bin/perl -MIO::Socket::UNIX -e 'chdir $ARGV[0] or die $!; IO::Socket::UNIX->new(Local => "agent.sock", Listen => 1) or die $!' "$AGENT_DIR"
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

@test "signing attaches the 1Password agent and preserves arguments" {
  run bash "$SCRIPT" -Y sign -n git -f "public identity.pub"
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=$AGENT_SOCKET"$'\n'* ]]
  [[ "$output" == *"arg=public identity.pub" ]]
}

@test "signing prefers the 1Password agent over an inherited agent" {
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/apple-agent"
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=$AGENT_SOCKET"$'\n'* ]]
}

@test "an inherited agent is kept when 1Password is unavailable" {
  rm "$AGENT_SOCKET"
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/forwarded-agent"
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=$SSH_AUTH_SOCK"$'\n'* ]]
}

@test "verification does not attach an agent" {
  run bash "$SCRIPT" -Y verify
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=unset"$'\n'* ]]
}

@test "a missing agent leaves the original signer behavior intact" {
  rm "$AGENT_SOCKET"
  export SIGN_EXIT=23
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

@test "a symlink cannot substitute for the agent socket" {
  mv "$AGENT_SOCKET" "$BATS_TEST_TMPDIR/real-socket"
  ln -s "$BATS_TEST_TMPDIR/real-socket" "$AGENT_SOCKET"
  run bash "$SCRIPT" -Y sign
  [ "$status" -eq 0 ]
  [[ "$output" == "socket=unset"$'\n'* ]]
}
