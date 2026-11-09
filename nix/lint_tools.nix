# Format and lint tools shared by the Home Manager profile and the dev shell, so
# local hooks and CI run the same versions from flake.lock.
{ pkgs, unstable }:
[
  pkgs.autocorrect
  unstable.dprint
  pkgs.selene
  pkgs.shellcheck
  pkgs.shfmt
  pkgs.stylua
]
