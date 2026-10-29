# ADR-0039: Require human approval on main

- Status: Superseded
- Date: 2026-10-29
- Superseded by: ADR-0040

In the context of agents opening pull requests as the GitHub App `furedea-agent[bot]` while the owner reviews and squash-merges them, facing a ruleset that required zero approvals so that "agents never merge" was only an instruction, we decided for one required approving review that is dismissed on push and requires approval of the last push, with the repository admin role bypassing only through a pull request, and against zero approvals or a bypass that permits direct pushes, to ensure nothing reaches main without the owner's approval since an author cannot approve their own pull request, accepting that the owner must re-approve after every push and that Renovate and workflow-opened pull requests wait for review.
