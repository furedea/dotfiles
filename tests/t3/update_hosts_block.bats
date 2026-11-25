#!/usr/bin/env bats
# Executable specifications for the managed /etc/hosts block that keeps T3 Code telemetry off.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  export TOOLS_PATH="$PATH"
  SCRIPT="$REPO_ROOT/scripts/t3/update_hosts_block.sh"
  HOSTS="$BATS_TEST_TMPDIR/hosts"
  BEGIN="# BEGIN t3-telemetry-block (managed by dotfiles; do not edit)"
  END="# END t3-telemetry-block"
  printf '%s\n' '127.0.0.1 localhost' '255.255.255.255 broadcasthost' '::1 localhost' >"$HOSTS"
  cp "$HOSTS" "$BATS_TEST_TMPDIR/original"
}

@test "a missing block is appended after the unchanged lines, blocking IPv4 and IPv6" {
  run "$SCRIPT" "$HOSTS" ingest.t3.codes api.axiom.co

  [ "$status" -eq 0 ]
  [ "$(head -n 3 "$HOSTS")" = "$(cat "$BATS_TEST_TMPDIR/original")" ]
  grep -qxF "0.0.0.0 ingest.t3.codes" "$HOSTS"
  grep -qxF ":: ingest.t3.codes" "$HOSTS"
  grep -qxF "0.0.0.0 api.axiom.co" "$HOSTS"
  grep -qxF ":: api.axiom.co" "$HOSTS"
}

@test "running twice leaves the file byte-identical" {
  "$SCRIPT" "$HOSTS" ingest.t3.codes
  cp "$HOSTS" "$BATS_TEST_TMPDIR/once"

  run "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 0 ]
  cmp "$HOSTS" "$BATS_TEST_TMPDIR/once"
}

@test "a changed host list replaces the block and keeps lines before and after it" {
  printf '%s\n' "$BEGIN" '0.0.0.0 old.example' "$END" '10.0.0.1 after.example' >>"$HOSTS"

  run "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 0 ]
  run ! grep -q old.example "$HOSTS"
  grep -qxF "0.0.0.0 ingest.t3.codes" "$HOSTS"
  [ "$(head -n 3 "$HOSTS")" = "$(cat "$BATS_TEST_TMPDIR/original")" ]
  [ "$(tail -n 1 "$HOSTS")" = "10.0.0.1 after.example" ]
  [ "$(grep -cF "$BEGIN" "$HOSTS")" -eq 1 ]
}

@test "a file without a trailing newline keeps its last line intact" {
  printf '127.0.0.1 localhost' >"$HOSTS"

  run "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 0 ]
  [ "$(head -n 1 "$HOSTS")" = "127.0.0.1 localhost" ]
  grep -qxF "$BEGIN" "$HOSTS"
}

@test "duplicated markers fail and leave the file unchanged" {
  printf '%s\n' "$BEGIN" "$END" "$BEGIN" "$END" >>"$HOSTS"
  cp "$HOSTS" "$BATS_TEST_TMPDIR/before"

  run --separate-stderr "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 1 ]
  cmp "$HOSTS" "$BATS_TEST_TMPDIR/before"
}

@test "an unpaired begin marker fails and leaves the file unchanged" {
  printf '%s\n' "$BEGIN" '10.0.0.1 keep.example' >>"$HOSTS"
  cp "$HOSTS" "$BATS_TEST_TMPDIR/before"

  run --separate-stderr "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 1 ]
  cmp "$HOSTS" "$BATS_TEST_TMPDIR/before"
}

@test "markers in the wrong order fail and leave the file unchanged" {
  printf '%s\n' "$END" '10.0.0.1 keep.example' "$BEGIN" >>"$HOSTS"
  cp "$HOSTS" "$BATS_TEST_TMPDIR/before"

  run --separate-stderr "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 1 ]
  cmp "$HOSTS" "$BATS_TEST_TMPDIR/before"
}

@test "a missing file fails without creating it" {
  run --separate-stderr "$SCRIPT" "$BATS_TEST_TMPDIR/absent" ingest.t3.codes

  [ "$status" -eq 1 ]
  [ ! -e "$BATS_TEST_TMPDIR/absent" ]
}

@test "a symlinked file fails and the link stays a link" {
  ln -s "$HOSTS" "$BATS_TEST_TMPDIR/link"

  run --separate-stderr "$SCRIPT" "$BATS_TEST_TMPDIR/link" ingest.t3.codes

  [ "$status" -eq 1 ]
  [ -L "$BATS_TEST_TMPDIR/link" ]
  cmp "$HOSTS" "$BATS_TEST_TMPDIR/original"
}

@test "the file mode is kept and no temporary file is left behind" {
  chmod 0644 "$HOSTS"

  run "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 0 ]
  [ "$(stat -c %a "$HOSTS" 2>/dev/null || stat -f %Lp "$HOSTS")" = "644" ]
  [ "$(find "$BATS_TEST_TMPDIR" -name 'hosts.*' | wc -l)" -eq 0 ]
}

@test "missing arguments print usage and fail" {
  run --separate-stderr "$SCRIPT" "$HOSTS"

  [ "$status" -eq 1 ]
  [[ "$stderr" == *Usage:* ]]
}

@test "an up-to-date file is not rewritten" {
  "$SCRIPT" "$HOSTS" ingest.t3.codes
  ls -i "$HOSTS" >"$BATS_TEST_TMPDIR/inode_before"

  run "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 0 ]
  [ "$(ls -i "$HOSTS")" = "$(cat "$BATS_TEST_TMPDIR/inode_before")" ]
}

@test "a named block lives beside the default block and each rewrite leaves the other alone" {
  "$SCRIPT" "$HOSTS" ingest.t3.codes
  HOSTS_BLOCK_NAME=app-telemetry-block run "$SCRIPT" "$HOSTS" us.i.posthog.com

  [ "$status" -eq 0 ]
  grep -qxF "# BEGIN app-telemetry-block (managed by dotfiles; do not edit)" "$HOSTS"
  grep -qxF "# END app-telemetry-block" "$HOSTS"
  grep -qxF "0.0.0.0 ingest.t3.codes" "$HOSTS"
  grep -qxF "0.0.0.0 us.i.posthog.com" "$HOSTS"

  HOSTS_BLOCK_NAME=app-telemetry-block "$SCRIPT" "$HOSTS" f.kiok.jp
  run ! grep -q us.i.posthog.com "$HOSTS"
  grep -qxF "0.0.0.0 f.kiok.jp" "$HOSTS"
  grep -qxF "0.0.0.0 ingest.t3.codes" "$HOSTS"
  [ "$(grep -cF "$BEGIN" "$HOSTS")" -eq 1 ]
}

@test "external tools come from TOOLS_PATH, not from the caller's PATH" {
  local _only_bash="$BATS_TEST_TMPDIR/only_bash"
  mkdir "$_only_bash"
  ln -s "$(command -v bash)" "$_only_bash/bash"

  run --separate-stderr env PATH="$_only_bash" TOOLS_PATH="$PATH" "$SCRIPT" "$HOSTS" ingest.t3.codes

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
}
