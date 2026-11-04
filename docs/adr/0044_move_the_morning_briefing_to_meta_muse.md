# ADR-0044: Move the morning briefing to Meta Muse

- Status: Accepted
- Date: 2026-11-04
- Supersedes: ADR-0042, ADR-0043

In the context of the local morning briefing (launchd, `claude -p`, Apple Mail, `gws`) failing to
deliver a readable report, facing Apple Mail wrapping bodies set through AppleScript as quoted text
(FB11734014) so that Spark cannot show them, we decided for running the briefing in Meta Muse in
the cloud with a single Gmail connector and a Google Calendar connector, after forwarding the four
mail accounts into Gmail, and against keeping the local launchd agent, ChatGPT Dots (unavailable on
the academic researcher plan), and Claude Duet (not offered in Japan), to remove the local
scheduler, the Mail automation, and the Google OAuth state, accepting that the briefing now depends
on a cloud service and on mail forwarding configured outside this repository.

Details that keep the decision testable:

- The `morning-briefing` launchd agent, its launcher script, the `secretary/` project, and the
  `gws` and `apple-mail-cli` packages and flake inputs are removed from this repository. The
  `furedea/apple-mail-cli` repository itself is untouched.
- Gmail forwarding, Muse settings, `~/.local/state/secretary`, and `~/.config/gws` live outside
  this repository and are removed or configured by hand.
- ADR-0019 is deprecated because the Apple Mail boundary no longer exists. Older secretary ADRs
  stay as historical records.
