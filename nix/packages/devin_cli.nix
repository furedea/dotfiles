{
  fetchurl,
  lib,
  stdenvNoCC,
  versionCheckHook,
}:

stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "devin-cli";
  version = "3000.10.31";

  src = fetchurl {
    url = "https://static.devin.ai/cli/${finalAttrs.version}/devin-${finalAttrs.version}-aarch64-apple-darwin.tar.gz";
    hash = "sha256-BR388p4PXLXwoHx1edyXJV/ufwLOTG/qzH1AZc52tb0=";
  };

  sourceRoot = ".";
  dontBuild = true;
  dontStrip = true;
  dontPatchELF = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -R . "$out"
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Official Devin CLI for local terminal sessions";
    homepage = "https://devin.ai/cli";
    license = lib.licenses.unfree;
    mainProgram = "devin";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
