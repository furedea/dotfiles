{
  fetchurl,
  lib,
  stdenvNoCC,
}:
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "terminal-browser";
  version = "0.6.0";

  src = fetchurl {
    url = "https://github.com/zenbu-labs/terminal-browser/releases/download/v${finalAttrs.version}/terminal-browser-darwin-arm64.tar.gz";
    hash = "sha256-0tGgYLYgjxyMUEoa+CXu0PsFv629iyPx4AZWGcV350k=";
  };

  sourceRoot = "terminal-browser";

  installPhase = ''
    runHook preInstall

    mkdir -p "$out"
    cp -R . "$out"

    runHook postInstall
  '';

  meta = {
    description = "Browser that runs directly inside a terminal";
    homepage = "https://terminal-browser.com";
    license = lib.licenses.mit;
    mainProgram = "terminal-browser";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
