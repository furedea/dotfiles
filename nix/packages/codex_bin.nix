{
  fetchurl,
  lib,
  stdenvNoCC,
  versionCheckHook,
}:

# Official build of the first codex release whose webpki crates distrust the
# compromised eMudhra intermediates; 0.163.0 trusts them even when SSL_CERT_FILE
# names a bundle without them. Return to llm-agents' codex once it has a stable
# release >= 0.164.0.
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "codex";
  version = "0.164.0-alpha.9";

  src = fetchurl {
    url = "https://github.com/openai/codex/releases/download/rust-v${finalAttrs.version}/codex-package-aarch64-apple-darwin.tar.gz";
    hash = "sha256-bNrBzIX9RCEysonFl68QB4NvCKqVXV2PZmYL+R5AjE8=";
  };

  sourceRoot = ".";
  dontBuild = true;
  dontStrip = true;

  # codex finds its resources relative to bin/ through codex-package.json.
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/libexec/codex" "$out/bin"
    cp -R bin codex-path codex-resources codex-package.json "$out/libexec/codex"
    ln -s ../libexec/codex/bin/codex "$out/bin/codex"
    ln -s ../libexec/codex/bin/codex-code-mode-host "$out/bin/codex-code-mode-host"
    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;
  # codex creates PATH aliases under its home even for --version.
  preInstallCheck = ''
    export HOME="$TMPDIR"
  '';
  versionCheckKeepEnvironment = [ "HOME" ];

  meta = {
    description = "Lightweight coding agent that runs in your terminal, official macOS build";
    homepage = "https://github.com/openai/codex";
    license = lib.licenses.asl20;
    mainProgram = "codex";
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
