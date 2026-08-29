{
  fetchurl,
  lib,
  stdenvNoCC,
}:
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "gh-stack";
  version = "0.1.0";

  src = fetchurl {
    url = "https://github.com/github/gh-stack/releases/download/v${finalAttrs.version}/darwin-arm64";
    hash = "sha256-XKmCQaJl1t4BgJXNrl88QNpcp4JFDuwOqRqo4+sYMQM=";
  };

  dontUnpack = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 "$src" "$out/bin/gh-stack"
    runHook postInstall
  '';

  meta = {
    description = "GitHub CLI extension for managing stacked pull requests";
    homepage = "https://github.com/github/gh-stack";
    license = lib.licenses.mit;
    mainProgram = "gh-stack";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
