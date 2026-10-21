{
  fetchurl,
  lib,
  stdenvNoCC,
  unzip,
  versionCheckHook,
}:

# Official build of dprint 0.64.1, whose webpki crates distrust the compromised
# eMudhra intermediates; dprint downloads plugins over TLS. Return to pkgs.dprint
# once the nixpkgs input has >= 0.64.1.
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "dprint";
  version = "0.64.1";

  src = fetchurl {
    url = "https://github.com/dprint/dprint/releases/download/${finalAttrs.version}/dprint-aarch64-apple-darwin.zip";
    hash = "sha256-0qbmfmqjCO0T0JYn6Kjo/izT9irrQG/mU9WbzsLCXEc=";
  };

  nativeBuildInputs = [ unzip ];
  sourceRoot = ".";
  dontBuild = true;
  dontStrip = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 -t "$out/bin" dprint
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;
  # dprint creates its cache directory even for --version.
  preInstallCheck = ''
    export HOME="$TMPDIR"
  '';
  versionCheckKeepEnvironment = [ "HOME" ];

  meta = {
    description = "Pluggable and configurable code formatting platform, official macOS build";
    homepage = "https://dprint.dev";
    license = lib.licenses.mit;
    mainProgram = "dprint";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
