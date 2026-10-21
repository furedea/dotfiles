{
  fetchurl,
  lib,
  stdenvNoCC,
  versionCheckHook,
}:

# Official build of uv 0.13.4, which drops the compromised emSign root from its
# bundled CA store. Return to pkgs.uv once the nixpkgs input has >= 0.13.4.
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "uv";
  version = "0.13.4";

  src = fetchurl {
    url = "https://github.com/astral-sh/uv/releases/download/${finalAttrs.version}/uv-aarch64-apple-darwin.tar.gz";
    hash = "sha256-4LHUdDzmTFXZ8PSkRK+muBElaABw7gToU/zQ9sHr+PE=";
  };

  dontBuild = true;
  dontStrip = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 -t "$out/bin" uv uvx
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Python package and project manager, official macOS build";
    homepage = "https://github.com/astral-sh/uv";
    license = with lib.licenses; [
      asl20
      mit
    ];
    mainProgram = "uv";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
