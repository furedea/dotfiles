{
  fetchurl,
  lib,
  stdenvNoCC,
  versionCheckHook,
}:

# Official build of the 2026-10-21 security release, which nixpkgs has only on
# staging. Return to unstable.nodejs_24 once nixpkgs-unstable has >= 24.22.1.
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "nodejs";
  version = "24.22.1";

  src = fetchurl {
    url = "https://nodejs.org/dist/v${finalAttrs.version}/node-v${finalAttrs.version}-darwin-arm64.tar.xz";
    hash = "sha256-ZUunneYVVkfiIyGTK0Xyocy3BZdswzfJuOJ4vrCFpig=";
  };

  dontBuild = true;
  dontStrip = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -R bin include lib share "$out"
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Node.js JavaScript runtime, official macOS build";
    homepage = "https://nodejs.org";
    license = lib.licenses.mit;
    mainProgram = "node";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
