---
status: proposed
date: 2026-11-22
related: [ADR-0041]
---

# Assemble the T3 desktop app bundle in dotfiles

## Context and Problem Statement

The T3 Code desktop app from `llm-agents` shows up as "Electron", with Electron's icon, in the Dock,
Cmd+Tab and the menu bar. Its `.app` is only a launcher that execs the binary inside nixpkgs'
`Electron.app`, and macOS names a process after the bundle that holds its executable. Issue #494
tracks the work; T3's code, version and provider PATH (including the signed Codex of ADR-0041)
should keep coming from `llm-agents`.

## Considered Options

- A dotfiles package (`nix/packages/t3code_desktop.nix`) that copies the `Electron.app` of the
    Electron `llm-agents` builds T3 against, renames it to T3, adds a launcher with the `llm-agents`
    wrappers' arguments and PATH, and re-signs the bundle ad-hoc.
- Keep the `llm-agents` `t3code-desktop` package and wait for an upstream fix.

## Decision Outcome

Chosen option: "A dotfiles package that copies `Electron.app` and renames it to T3", because the
running Electron then lives in a bundle whose name, identifier and icon are T3's, while only the
bundle assembly leaves `llm-agents`. Electron comes from the `llm-agents` nixpkgs input, not the
dotfiles one, so T3 runs on the Electron it was built for. Waiting for upstream leaves the wrong
name and icon in place with no date.

### Consequences

- Good, because the Dock, Cmd+Tab and the menu bar show T3 Code (Beta) and T3's icon.
- Good, because T3's code and version still update with `llm-agents`, and the launchd server's
    `t3codePackage` is unchanged.
- Bad, because dotfiles duplicates the `llm-agents` wrappers' arguments and PATH; the
    `t3-desktop-app-bundle` check fails when they, the app directory, or the Electron version drift.
- Bad, because the store holds a second, ad-hoc signed copy of `Electron.app`, and macOS asks for
    notification permission again after the identifier and signature change.
- Revert to the `llm-agents` package once upstream assembles a T3-named bundle itself.
