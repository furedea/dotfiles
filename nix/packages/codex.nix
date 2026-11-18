{
  fetchurl,
  lib,
  stdenv,
  versionCheckHook,
}:

# Installs OpenAI's Developer ID signed release unmodified. Stripping, patching, or re-signing
# would replace the vendor signature and break the Keychain ACL match across updates.
stdenv.mkDerivation (finalAttrs: {
  pname = "codex";
  version = "0.167.0";

  src = fetchurl {
    url = "https://github.com/openai/codex/releases/download/rust-v${finalAttrs.version}/codex-package-aarch64-apple-darwin.tar.gz";
    hash = "sha256-r0XtRdlA15mICWIsHAKW0wmO19f61pUoRCLCKL1FRRc=";
  };

  sourceRoot = ".";
  dontBuild = true;
  dontFixup = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/libexec/codex" "$out/bin"
    cp -R bin codex-path codex-resources codex-package.json "$out/libexec/codex/"
    for program in codex codex-code-mode-host codex-exec-server; do
      ln -s "$out/libexec/codex/bin/$program" "$out/bin/$program"
    done
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  installCheckPhase = ''
    runHook preInstallCheck
    for program in bin/codex bin/codex-code-mode-host bin/codex-exec-server codex-path/rg; do
      signature="$(/usr/bin/codesign --display --verbose=2 "$out/libexec/codex/$program" 2>&1)"
      grep --quiet '^TeamIdentifier=2DC432GLL2$' <<<"$signature" ||
        { echo "$program lost the OpenAI team identifier" >&2; exit 1; }
      grep --quiet '^Authority=Developer ID Application: ' <<<"$signature" ||
        { echo "$program lost the Developer ID authority" >&2; exit 1; }
      /usr/bin/codesign --verify --strict "$out/libexec/codex/$program"
    done
    runHook postInstallCheck
  '';

  meta = {
    description = "OpenAI Codex CLI from the official Developer ID signed release";
    homepage = "https://github.com/openai/codex";
    license = lib.licenses.asl20;
    mainProgram = "codex";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
