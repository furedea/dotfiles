# ADR-0037: Hand approved lanes to Herdr sessions

- Status: Accepted
- Date: 2026-10-17

In the context of a delivery flow whose only human gates are plan approval and merging, and a
sandbox that confines each session's writes to the directory it started in, facing task
worktrees a session could not write, Herdr commands that always asked because Herdr runs outside
the sandbox, and keystrokes to existing panes that would run outside it, we decided for handing
each lane of an approved plan to a new Herdr task worktree and a Claude or Codex session started
there, for allowing exactly the forms that create a worktree or pane, start such an agent without
extra arguments, and prompt an agent this session started, recorded per session and refused for
names another agent already holds, and against allowing Herdr control broadly, widening the
sandbox to sibling checkouts, or keeping every hand-off behind a prompt, to let approved work run
to a pull request unattended while every child keeps the same sandbox and hooks, accepting that
repository trust, pane environments, other agent kinds, renames, and driving existing panes still
prompt, and that a session without Herdr falls back to one lane in the current checkout.
