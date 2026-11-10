{
  fetchurl,
  lib,
  stdenv,
  versionCheckHook,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "moshi-hook";
  version = "0.4.53";

  src = fetchurl {
    url = "https://cdn.getmoshi.app/hook/v${finalAttrs.version}/moshi-hook_Darwin_arm64.tar.gz";
    hash = "sha256-A+3A8n9c4hm7HPR85xMRGpddhtGw2r2hgWq7Ssjanbs=";
  };

  sourceRoot = ".";
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin"
    install -m755 moshi-hook "$out/bin/moshi-hook"
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Bridge between AI coding agents and the Moshi mobile app";
    homepage = "https://getmoshi.app";
    license = lib.licenses.unfree;
    mainProgram = "moshi-hook";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
