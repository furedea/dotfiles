{
  electron_44,
  lib,
  makeBinaryWrapper,
  stdenvNoCC,
  t3code,
}:

# macOS names the Dock and Cmd+Tab entry after the bundle that holds the running binary, so
# llm-agents' launcher, which execs nixpkgs' Electron.app, shows up as "Electron". This copies
# that Electron.app, renames it to T3, and execs the copy's own Electron with T3's app directory.
let
  inherit (t3code.unwrapped) appName;
  upstreamApp = "${t3code.desktop}/Applications/${appName}.app";
  appDirectory = "${t3code.unwrapped.desktop}/libexec/t3code/apps/desktop";
in
stdenvNoCC.mkDerivation {
  pname = "t3code-desktop";
  inherit (t3code) version;

  dontUnpack = true;
  # Fixup would strip or rewrite Mach-O files after the ad-hoc signature is applied.
  dontFixup = true;

  nativeBuildInputs = [ makeBinaryWrapper ];

  installPhase = ''
    runHook preInstall

    app="$out/Applications/${appName}.app"
    mkdir -p "$out/Applications" "$out/bin"
    cp -R ${electron_44}/Applications/Electron.app "$app"
    chmod -R u+w "$app"

    install -m444 "${upstreamApp}/Contents/Resources/t3code.icns" "$app/Contents/Resources/t3code.icns"
    plist="$app/Contents/Info.plist"
    identifier=$(/usr/bin/plutil -extract CFBundleIdentifier raw -o - "${upstreamApp}/Contents/Info.plist")
    /usr/bin/plutil -replace CFBundleName -string "${appName}" "$plist"
    /usr/bin/plutil -replace CFBundleDisplayName -string "${appName}" "$plist"
    /usr/bin/plutil -replace CFBundleIdentifier -string "$identifier" "$plist"
    /usr/bin/plutil -replace CFBundleIconFile -string t3code.icns "$plist"
    /usr/bin/plutil -replace CFBundleExecutable -string "${appName}" "$plist"

    # Same arguments and PATH as llm-agents' two wrappers, which keeps the signed Codex (ADR-0041).
    makeWrapper "$app/Contents/MacOS/Electron" "$app/Contents/MacOS/${appName}" \
      --add-flags ${lib.escapeShellArg appDirectory} \
      --prefix PATH : ${lib.escapeShellArg (lib.makeBinPath t3code.providerPackages)} \
      --inherit-argv0
    ln -s "../Applications/${appName}.app/Contents/MacOS/${appName}" "$out/bin/t3code-desktop"
    ln -s ${t3code.desktop}/share "$out/share"

    # Editing Info.plist and adding the launcher invalidate the copied signature.
    /usr/bin/codesign --force --deep --sign - "$app"

    runHook postInstall
  '';

  meta = t3code.meta // {
    description = "T3 Code desktop app bundled under its own name and icon";
    mainProgram = "t3code-desktop";
    platforms = [ "aarch64-darwin" ];
  };
}
