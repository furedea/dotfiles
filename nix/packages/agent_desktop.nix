{
  fetchurl,
  lib,
  stdenvNoCC,
  versionCheckHook,
}:

stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "agent-desktop";
  version = "1.2.0";

  src = fetchurl {
    url = "https://github.com/vercel-labs/agent-desktop/releases/download/v${finalAttrs.version}/agent-desktop-v${finalAttrs.version}-aarch64-apple-darwin.tar.gz";
    hash = "sha256-IZgTQouxrY3srhcvrtBcWWSiQVFw30AuJ4bM+mRSuoI=";
  };

  sourceRoot = ".";
  dontBuild = true;
  dontStrip = true;
  dontPatchELF = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 agent-desktop agent-desktop-macos-helper -t "$out/bin"
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Desktop automation CLI for AI agents through the macOS accessibility tree";
    homepage = "https://github.com/vercel-labs/agent-desktop";
    license = lib.licenses.asl20;
    mainProgram = "agent-desktop";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
