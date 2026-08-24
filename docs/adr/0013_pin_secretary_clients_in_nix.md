# ADR-0013: Pin secretary clients in Nix

- Status: Superseded
- Date: 2026-08-24

In the context of unattended Hermes routines that depend on `ical` and `xurl`,
facing their absence from the locked nixpkgs revision, automatic Homebrew
upgrades, and an `xurl` source archive that omits the native XChat assets used
by its release build, we decided for hash-pinned Nix packages in Home Manager,
building `ical` from source and installing the official signed `xurl` release
artifact, and against third-party Homebrew taps or an incomplete `xurl` source
build, to keep client versions reproducible without dropping upstream
functionality, accepting maintenance of custom derivations and explicit
version upgrades.
