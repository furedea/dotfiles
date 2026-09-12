#!/usr/bin/env bats
# Executable specifications for the persistent Rust language server service.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Home Manager provides a persistent mux with project toolchain forwarding" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config" --apply '
    config: let
      service = config.launchd.agents.lspmux;
      settings = builtins.fromTOML config.home.file."Library/Application Support/lspmux/config.toml".text;
    in {
      enabled = service.enable && service.config.RunAtLoad && service.config.KeepAlive;
      command = service.config.ProgramArguments;
      packages = map (package: package.pname or package.name) config.home.packages;
      analyzer = toString config.home.file.".local/bin/rust-analyzer".source;
      inherit settings;
    }'

  [ "$status" -eq 0 ]
  run jq -e '
    .enabled
    and (.command[0] | startswith("/nix/store/"))
    and .command[1] == "server"
    and (.packages | index("lspmux") != null)
    and (.analyzer | contains("rust-analyzer-unwrapped"))
    and .settings.instance_timeout == 300
    and (["PATH", "RUSTUP_TOOLCHAIN", "RUSTC", "RUST_SRC_PATH", "NIX_CFLAGS_COMPILE", "SDKROOT"]
      - .settings.pass_environment | length == 0)
  ' <<<"$output"

  [ "$status" -eq 0 ]
}
