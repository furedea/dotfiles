# The nixpkgs `atuin` builds only the client; the sync server is another binary of the same
# workspace. Reusing its source and vendored dependencies keeps the server on the client's version.
{
  atuin,
  openssl,
  pkg-config,
  rustPlatform,
  sqlite,
  zstd,
}:
rustPlatform.buildRustPackage {
  pname = "atuin-server";
  inherit (atuin) version src cargoDeps;

  cargoBuildFlags = [
    "--package"
    "atuin-server"
  ];

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [
    openssl
    sqlite
    zstd
  ];

  # The workspace tests belong to the nixpkgs atuin build; this one only ships the server binary.
  doCheck = false;

  meta = atuin.meta // {
    description = "Atuin sync server";
    mainProgram = "atuin-server";
  };
}
