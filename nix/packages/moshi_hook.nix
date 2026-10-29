{
  fetchurl,
  lib,
  stdenv,
  versionCheckHook,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "moshi-hook";
  version = "0.4.41";

  src = fetchurl {
    url = "https://cdn.getmoshi.app/hook/v${finalAttrs.version}/moshi-hook_Darwin_arm64.tar.gz";
    hash = "sha256-H2X9Uqvl2CtF0C2Ba3v3felBpAbr4iP08NxpUegMH20=";
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
