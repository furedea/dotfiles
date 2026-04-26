#!/bin/bash
# Claude Code PreToolUse hook: block destructive / review-bypassing git operations.
#
# Covered:
#   - git push --force / -f / --force-with-lease     (force push)
#   - git push ... +refspec                          (force push via + prefix)
#   - git push to main/master (explicit or implicit via current branch)
#   - gh pr merge --admin                            (bypasses review)
#
# Exit code 0 = allow, exit code 2 = block.

set -euCo pipefail

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/shell_parse.sh"

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Detect shell-wrapper commands that execute an arbitrary inner string
# (bash -c, sh -c, zsh -c, the e-v-a-l builtin). This hook cannot statically
# parse the inner shell, so we fail closed when the wrapper carries tokens
# that could indicate a dangerous git operation.
function wrapper_unsafe() {
  local _seg="$1"
  # Match `c` anywhere in a combined short-option cluster so that forms
  # like `bash -xc`, `bash -cx`, `bash -evc` all get caught, not just the
  # trailing-c case.
  if ! printf '%s\n' "$_seg" | grep -qE '(^|[[:space:]])((/bin/|/usr/bin/)?(ba|z)?sh[[:space:]]+-[^[:space:]]*c[^[:space:]]*([[:space:]]|$)|eval([[:space:]]|$))'; then
    return 1
  fi
  if printf '%s\n' "$_seg" | grep -qE '(git[[:space:]]+push|gh[[:space:]]+pr[[:space:]]+merge|--force|--force-with-lease|[[:space:]]\+?(main|master)([[:space:]]|$)|--admin)'; then
    return 0
  fi
  return 1
}

# Analyze a `git push` segment. Returns 2 if dangerous, 0 otherwise.
# Parses options robustly: handles `--`, flags with a separate argument
# (-u / --set-upstream / --repo / --receive-pack / --exec), flag=value
# forms, and multiple refspecs.
function analyze_git_push() {
  local _seg="$1"
  local _rest _current_branch _remote _refspec _target
  local -a _raw_tokens _positional _refspecs
  local _i _token

  # --- --force / --force-with-lease ---
  if printf '%s\n' "$_seg" | grep -qE '(^|[[:space:]])(-f|--force|--force-with-lease)([[:space:]]|=|$)'; then
    cat >&2 <<ERRMSG
BLOCKED: force-push flag detected.

Segment: $_seg

Why: Force push rewrites history and can destroy teammates' commits. Even
     --force-with-lease has a narrow safety window; deny by default.

What to do:
  Claude Code: Push without --force. If history rewrite is genuinely required,
               ask the user to run it manually.
  User: Run 'git push --force' manually if you decide it is needed.
ERRMSG
    return 2
  fi

  # --- Parse positional args ---
  _rest=$(printf '%s\n' "$_seg" | sed -E 's/^[[:space:]]*git[[:space:]]+push([[:space:]]|$)//; s/[[:space:]]+(2>&1|2>\/dev\/null|>&2)[[:space:]]*$//; s/[[:space:]]+$//')

  _raw_tokens=()
  _positional=()
  _refspecs=()

  IFS=' ' read -r -a _raw_tokens <<<"$_rest"

  _i=0
  while [ "$_i" -lt "${#_raw_tokens[@]}" ]; do
    _token="${_raw_tokens[$_i]}"
    if [ -z "$_token" ]; then
      _i=$((_i + 1))
      continue
    fi
    case "$_token" in
      --)
        _i=$((_i + 1))
        while [ "$_i" -lt "${#_raw_tokens[@]}" ]; do
          [ -n "${_raw_tokens[$_i]}" ] && _positional+=("${_raw_tokens[$_i]}")
          _i=$((_i + 1))
        done
        break
        ;;
      --repo | --receive-pack | --exec)
        # These flags consume the next token as their argument.
        _i=$((_i + 2))
        ;;
      -u | --set-upstream)
        # Boolean flags; do not consume the next token.
        _i=$((_i + 1))
        ;;
      --*=* | -*)
        _i=$((_i + 1))
        ;;
      *)
        _positional+=("$_token")
        _i=$((_i + 1))
        ;;
    esac
  done

  # First positional is remote, rest are refspecs.
  _remote=""
  [ "${#_positional[@]}" -ge 1 ] && _remote="${_positional[0]}"
  [ "${#_positional[@]}" -ge 2 ] && _refspecs=("${_positional[@]:1}")

  # --- Implicit target (no refspec): use current branch ---
  if [ "${#_refspecs[@]}" -eq 0 ]; then
    _current_branch=$(git branch --show-current 2>/dev/null || printf '')
    _current_branch="${_current_branch#refs/heads/}"
    if [ "$_current_branch" = "main" ] || [ "$_current_branch" = "master" ]; then
      cat >&2 <<ERRMSG
BLOCKED: push target is '$_current_branch'.

Segment: $_seg

Why: All changes must go through a pull request. Direct push to
     '$_current_branch' bypasses review and may trigger production CI
     unexpectedly.

What to do:
  Claude Code: Switch to a feature branch and open a PR via 'gh pr create'.
  User: If a direct push is truly needed (emergency revert, etc.), run it
        manually in your terminal.
ERRMSG
      return 2
    fi
    return 0
  fi

  # --- Explicit refspecs: check each ---
  for _refspec in "${_refspecs[@]}"; do
    # +refspec force push
    if [[ "$_refspec" == +* ]]; then
      cat >&2 <<ERRMSG
BLOCKED: '+refspec' force push detected.

Segment: $_seg

Why: The '+' prefix on a refspec forces a non-fast-forward update,
     equivalent to --force for that refspec.

What to do:
  Claude Code: Push without the '+' prefix.
  User: Run the force push manually if you decide it is needed.
ERRMSG
      return 2
    fi

    _target=""
    if [[ "$_refspec" == *:* ]]; then
      _target="${_refspec##*:}"
    elif [ "$_refspec" = "HEAD" ]; then
      _target=$(git branch --show-current 2>/dev/null || printf '')
    else
      _target="$_refspec"
    fi
    _target="${_target#refs/heads/}"

    [ -z "$_target" ] && continue

    if [ "$_target" = "main" ] || [ "$_target" = "master" ]; then
      cat >&2 <<ERRMSG
BLOCKED: push target is '$_target'.

Segment: $_seg

Why: All changes must go through a pull request. Direct push to '$_target'
     bypasses review and may trigger production CI unexpectedly.

What to do:
  Claude Code: Switch to a feature branch and open a PR via 'gh pr create'.
  User: If a direct push is truly needed (emergency revert, etc.), run it
        manually in your terminal.
ERRMSG
      return 2
    fi
  done

  return 0
}

# Per-segment analysis. Returns 2 if segment is dangerous, 0 otherwise.
function analyze_segment() {
  local _seg="$1"
  local _trimmed
  _trimmed=$(printf '%s\n' "$_seg" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')
  [ -z "$_trimmed" ] && return 0

  # --- shell wrapper carrying destructive tokens (fail closed) ---
  if wrapper_unsafe "$_trimmed"; then
    cat >&2 <<ERRMSG
BLOCKED: shell wrapper (bash -c / sh -c / the e-v-a-l builtin) with destructive git tokens.

Segment: $_trimmed

Why: This hook cannot statically analyze commands run through a shell wrapper,
     and the segment carries tokens suggesting a git push / gh pr merge with
     --force, --admin, main, or master. Failing closed.

What to do:
  Claude Code: Rewrite without the shell wrapper so the command is directly
               visible, or ask the user to run it manually.
  User: Run the command manually in your terminal if it is safe.
ERRMSG
    return 2
  fi

  # --- gh pr merge --admin ---
  if printf '%s\n' "$_trimmed" | grep -qE '^gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)' &&
    printf '%s\n' "$_trimmed" | grep -qE '(^|[[:space:]])--admin([[:space:]]|=|$)'; then
    cat >&2 <<ERRMSG
BLOCKED: 'gh pr merge --admin' bypasses required reviews and branch protection.

Segment: $_trimmed

Why: Admin merge is reserved for genuine emergencies and should be a human
     decision, not an agent decision.

What to do:
  Claude Code: Merge without --admin. If admin merge is genuinely required,
               stop and ask the user.
  User: Run 'gh pr merge --admin' manually if you decide it is needed.
ERRMSG
    return 2
  fi

  # --- git push analysis ---
  if printf '%s\n' "$_trimmed" | grep -qE '^git[[:space:]]+push([[:space:]]|$)'; then
    analyze_git_push "$_trimmed"
    return $?
  fi

  return 0
}

# Iterate over segments; block on first dangerous match.
while IFS= read -r segment; do
  if ! analyze_segment "$segment"; then
    exit 2
  fi
done <<<"$(split_command_segments "$COMMAND")"

exit 0
