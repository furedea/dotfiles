---
status: proposed
date: 2026-11-22
---

# ADR-0046: Assemble the T3 desktop app bundle in dotfiles

In the context of the T3 Code desktop app from `llm-agents`
([#494](https://github.com/furedea/dotfiles/issues/494)), facing its `.app` being a launcher that
execs the binary inside nixpkgs' `Electron.app`, so that macOS names the running process after that
bundle and shows "Electron" with Electron's icon in the Dock, Cmd+Tab and the menu bar, we decided
for a dotfiles package (`nix/packages/t3code_desktop.nix`) that copies the `Electron.app` of the
Electron `llm-agents` builds T3 against, renames it to T3 with T3's identifier and icon, puts a
launcher with the `llm-agents` wrappers' arguments and PATH in it, and re-signs it ad-hoc, and
against keeping the `llm-agents` `t3code-desktop` package or waiting for an upstream change, so that
the running Electron lives in a bundle that is T3 while T3's code, version and provider PATH
(including the signed Codex of ADR-0041) still come from `llm-agents`, accepting that dotfiles now
duplicates the wrappers' arguments, takes Electron from the `llm-agents` nixpkgs input, and stores a
second copy of `Electron.app`; the `t3-desktop-app-bundle` check fails when the PATH, app directory
or Electron version drifts from `llm-agents`.
