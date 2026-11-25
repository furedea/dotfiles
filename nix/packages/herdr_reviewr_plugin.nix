{
  fetchFromGitHub,
  lib,
  libgit2,
  oniguruma,
  pkg-config,
  rustPlatform,
}:

# A Herdr plugin directory for `herdr plugin link`: the upstream release installer downloads a
# prebuilt binary that is never the pinned commit, so the binary is built from the pinned source.
rustPlatform.buildRustPackage {
  pname = "herdr-reviewr-plugin";
  version = "0.36.2";

  src = fetchFromGitHub {
    owner = "persiyanov";
    repo = "herdr-reviewr";
    rev = "4c090225af706bf3aaa24b39fea890a72994f40f";
    hash = "sha256-bQiIj9HpkwCtoR5SoyDah0w/f15fUVtSqxMZ3zxLOy8=";
  };

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [
    libgit2
    oniguruma
  ];
  env.RUSTONIG_SYSTEM_LIBONIG = "1";

  cargoHash = "sha256-UAqKwl9xYAAF9J8g+tP4WqkOgvEhNJut7vjO2R4Fehc=";

  # The unit tests run git and the herdr CLI against a live checkout.
  doCheck = false;

  postInstall = ''
    plugin="$out/share/herdr-plugin"
    mkdir -p "$plugin/bin" "$plugin/herdr"
    mv "$out/bin/herdr-reviewr" "$plugin/bin/"
    cp herdr/pane.sh "$plugin/herdr/"
    # Drop the [[build]] table so that linking never downloads a binary.
    awk '/^\[\[build\]\]/ { skip = 1; next } /^\[/ { skip = 0 } !skip' herdr-plugin.toml >"$plugin/herdr-plugin.toml"
    rmdir "$out/bin"
  '';

  meta = {
    description = "Herdr reviewr plugin built from the pinned source";
    homepage = "https://github.com/persiyanov/herdr-reviewr";
    license = lib.licenses.mit;
  };
}
