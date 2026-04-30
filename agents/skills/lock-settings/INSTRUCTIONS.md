# Lock Settings

- **Edit/Write deny rules** block Claude's built-in Edit and Write tools.
- **Sandbox `denyWrite`** provides OS-level (kernel/Seatbelt) enforcement that blocks Bash subprocesses (`sed -i`, `echo >`, `rm`, etc.) from writing to those files.

Both layers are required for defense-in-depth.

---

## Step 1 — Identify files to protect

Scan the repository for files that should be protected from Claude Code modification. Start with these known locations, and add any other security-sensitive or configuration files you discover:

- `.claude/settings.json`
- `.claude/settings.local.json`
- `.claude/hooks/*.sh`
- `.githooks/*`
- `scripts/install-hooks.sh`

Use your judgement to identify additional files that need protection — for example, CI/CD configs, deployment scripts, or other files where unintended modification could compromise security or break workflows.

Read the current `.claude/settings.json` to check which files already have deny rules and `sandbox.filesystem.denyWrite` entries. Only add rules for files that are **not yet protected**.

---

## Step 2 — Create a branch and add deny rules

1. Create a new branch named after what is being locked (e.g., `chore/lock-hooks-and-settings`, `chore/lock-ci-configs`).
2. Add to `.claude/settings.json` for each unprotected file:
   - **Permission deny rules** (under `permissions.deny`):
     - `Edit(<path>)` — block the Edit tool
     - `Write(<path>)` — block the Write tool
   - **Sandbox deny rule** (under `sandbox.filesystem.denyWrite`):
     - `./<path>` — block Bash-level writes at the OS level
   - **Important**: List individual files, not directories. Directory-level `denyWrite` would prevent creating new files in that directory.
3. Commit with message: `chore: add deny rules for settings and hook files`

---

## Step 3 — Create the PR

Run `/create-pr` to push and open a pull request. The PR description should list exactly which files were locked and why.
