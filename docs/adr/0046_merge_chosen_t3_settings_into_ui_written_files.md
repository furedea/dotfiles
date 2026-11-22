---
status: proposed
date: 2026-11-22
related: [ADR-0002, ADR-0045]
---

# Merge chosen T3 settings into the files T3 writes from its UI

## Context and Problem Statement

The user chose values for some T3 Code settings (Issue #489, step 5) and wants both MacBooks to
get them from this repository. T3 keeps them in JSON files under `~/.t3/userdata/` that it also
rewrites from its settings UI: the server rewrites `settings.json` and `keybindings.json` and
reloads both when they change; the desktop app reads `client-settings.json` and
`desktop-settings.json` when it starts and rewrites the whole document from memory on any change.
Settings the user did not choose must stay free to change in the UI.

## Considered Options

- A Home Manager activation script merges only the chosen keys into each file with `jq`, replacing
    the file atomically.
- Link the files from the Nix store or the working tree (`home.file`).
- Leave the settings to the UI on each machine.

## Decision Outcome

Chosen option: "merge only the chosen keys at activation", because it is the only option that
declares the chosen values while T3 keeps writing the rest: a store link is read-only, so every
save from the UI fails, and a working-tree link would commit every UI change to this repository.
It follows ADR-0002, which manages Herdr plugin state through activation for the same reason. The
server settings and `localEnvironmentEnabled: false` go only to the host with the T3 server
(ADR-0045). Values T3 keeps in the desktop app's Local Storage, such as the theme, are not
managed, since no file merge reaches them safely.

### Consequences

- Good, because the chosen values return after a reinstall or on a new machine, and unchosen keys
    stay as the UI left them.
- Bad, because a managed key changed in the UI silently returns to the declared value at the next
    switch; the declared value is the one to change.
- Bad, because the desktop app holds its settings in memory: it must be quit before a switch, or
    reopened after it without changing a setting first, or it overwrites the merged file.
- Bad, because the merge depends on T3's file shapes and key names, which a T3 update can change;
    a file that does not parse is left unchanged with a warning, and the check in `nix/checks.nix`
    pins the expected documents.
