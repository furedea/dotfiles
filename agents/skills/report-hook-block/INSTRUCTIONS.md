# Report Hook Block

## Step 1 — Identify the Block

Gather the following from the current conversation context:

1. **Which hook blocked the action** — identify the hook script name (e.g., `command-allowlist.sh`, `prevent-secret-commit.sh`, `block-no-verify.sh`).
2. **What command or action was attempted** — the exact command or tool call that was blocked.
3. **The error message** — the full BLOCKED message returned by the hook.

If any of these are unclear from context, ask the user to clarify before proceeding.

---

## Step 2 — Determine the Hook File and Current Rule

Read the relevant hook script to understand why the block occurred:

- `.claude/hooks/command-allowlist.sh` — check `ALLOWED_PATTERNS` and `GOVERNED_PREFIXES`
- `.claude/hooks/prevent-secret-commit.sh` — check the sensitive file patterns
- `.claude/hooks/block-no-verify.sh` — check what flags are blocked

Identify the specific rule or missing pattern that caused the rejection.

---

## Step 3 — Draft a Proposed Fix

Based on your analysis, draft a concrete proposal. Examples:

- For `command-allowlist.sh`: a new regex pattern to add to `ALLOWED_PATTERNS`
- For `prevent-secret-commit.sh`: an exclusion for a false-positive filename pattern
- For `block-no-verify.sh`: a justification for why the blocked flag should be reconsidered

The proposal must be specific enough that someone can implement it directly.

---

## Step 4 — Create the GitHub Issue

Run `gh issue create` with:

- **Title**: `hook-policy: <hook-name> blocks <short description of action>`
- **Labels**: Add `hook-policy` label. If the label does not exist yet, create it first with `gh label create hook-policy --description "Hook rule is too restrictive or needs updating" --color D93F0B`.
- **Body**: Use a HEREDOC with `--body-file` to preserve formatting:

```bash
gh issue create --title "hook-policy: ..." --label hook-policy --body-file - <<'EOF'
## Blocked Action

**Hook:** `<hook-script-name>`
**Command attempted:** `<the command or action>`
**Error message:**

    <full error message, indented 4 spaces>

## Why This Is a Problem

<1-2 sentences explaining why this block is too restrictive for the current use case>

## Proposed Fix

<concrete change — e.g., a new regex pattern, an exclusion rule, or a policy change>

## Context

<brief description of what work was being done when this block occurred>
EOF
```

Print the issue URL when done.

---

## Step 5 — Resume Work

After the issue is created, suggest an alternative approach to the user so they can continue working without the blocked action. Do not leave them stuck.
