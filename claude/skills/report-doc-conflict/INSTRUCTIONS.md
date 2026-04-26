# Report Documentation Conflict

## Step 1 — Identify the Conflicting Passages

Based on the user's description and the current conversation context, locate the specific conflicting instructions. You need:

1. **File A** — the path and relevant passage (with line numbers)
2. **File B** — the path and relevant passage (with line numbers) that contradicts File A
3. **The contradiction** — a clear explanation of how the two instructions conflict

The files may include any project markdown: `CLAUDE.md`, skill files (`SKILL.md`), ADRs (`docs/adr/`), planning docs (`docs/plans/`), or files under `docs/claude/`.

Read the relevant files to confirm the exact text and line numbers. Do not rely on memory alone — verify by reading.

If the conflict is within a single file (two sections contradict each other), that is also valid.

---

## Step 2 — Assess the Impact

Determine how the contradiction affected work:

- What task was being performed when the conflict was discovered?
- Which instruction was followed, and which was not?
- Did this cause wasted effort, incorrect implementation, or a complete block?

---

## Step 3 — Draft a Recommended Resolution

Propose how the conflict should be resolved. Options include:

- **Update File A** to align with File B (with rationale)
- **Update File B** to align with File A (with rationale)
- **Update both** to a new consistent instruction
- **Flag for discussion** if the right answer is unclear

Be specific — quote the proposed new text if possible.

---

## Step 4 — Create the GitHub Issue

Run `gh issue create` with:

- **Title**: `docs-conflict: <short summary of the contradiction>`
- **Labels**: Add `docs-conflict` label. If the label does not exist yet, create it first with `gh label create docs-conflict --description "Contradictory instructions in project documentation" --color 0075CA`.
- **Body**: Use a HEREDOC with `--body-file` to preserve formatting:

```bash
gh issue create --title "docs-conflict: ..." --label docs-conflict --body-file - <<'EOF'
## Conflicting Instructions

### Passage 1
**File:** `<file-path>` (lines X–Y)

    <quoted text, indented 4 spaces>

### Passage 2
**File:** `<file-path>` (lines X–Y)

    <quoted text, indented 4 spaces>

## The Contradiction

<clear explanation of how these instructions conflict>

## Impact

<how this affected the current work — what task was blocked or confused>

## Recommended Resolution

<specific proposal for how to resolve the conflict>
EOF
```

Print the issue URL when done.

---

## Step 5 — Agree on a Workaround

After the issue is created, discuss with the user which instruction to follow for now so work can continue. Do not leave the ambiguity unresolved for the current task.
