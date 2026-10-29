# ADR-0040: Drop last-push approval on main

- Status: Accepted
- Date: 2026-10-29
- Supersedes: ADR-0039

In the context of the owner being the only human approver while workflow-file changes must be pushed by the owner because the agent token cannot push them, facing a ruleset that required approval of the last push so that the owner became the last pusher and GitHub refused their own approval, we decided for keeping one required approving review that is dismissed on push and the admin bypass only through a pull request, while no longer requiring approval of the last push, and against keeping last-push approval, to keep every pull request approvable by the owner since the agent bot cannot approve its own pull request and dismissal on push already resets an approval given before any later push, accepting that a pushed commit needs no approver other than the one who approved the latest state.
