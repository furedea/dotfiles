#!/usr/bin/env bats
# Executable specifications for globally available language toolchains.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Home Manager provides global fallback runtimes without mutable installers" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config" --apply '
    config: {
      packages = map (package: package.pname or package.name) config.home.packages;
      activations = builtins.attrNames config.home.activation;
    }'

  [ "$status" -eq 0 ]
  run jq -e '
    (["python3", "uv", "nodejs", "pnpm", "cargo", "rustc", "clippy", "rustfmt"]
      - .packages | length == 0)
    and (.packages | index("rustup") == null)
    and (.activations | index("rustupInit") == null)
    and (.activations | index("uvPythonInstall") == null)
  ' <<<"$output"

  [ "$status" -eq 0 ]
}
