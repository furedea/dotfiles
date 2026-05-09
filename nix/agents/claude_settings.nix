{ lib, dotfilesDir }:
let
  commandPolicy = import ./command_policy.nix { inherit lib; };

  baseSettings = builtins.fromJSON (builtins.readFile ../../claude/settings.base.json);

  isBashPermission = permission: lib.hasPrefix "Bash(" permission;

  nonBashPermissions =
    permissions: builtins.filter (permission: !(isBashPermission permission)) permissions;

  # Enumerate every regular file under a source directory and return the
  # paths relative to it. Used to expand the security harness into explicit
  # deny entries — listing individual files (rather than the directory)
  # avoids blocking new-file creation under the same parent.
  filesUnder =
    root:
    let
      prefix = toString root + "/";
    in
    map (path: lib.removePrefix prefix (toString path)) (lib.filesystem.listFilesRecursive root);

  hookFiles = filesUnder ../../agents/hooks;

  # Basename of the dotfiles checkout (e.g. `dotfiles`). Used to build glob
  # patterns that match the same files regardless of where the repository
  # is cloned, so deny rules don't carry username- or ghq-specific paths.
  dotfilesName = baseNameOf dotfilesDir;

  # Files Claude must never modify: the PreToolUse security harness plus
  # the configuration that binds it. Skill scripts are deliberately
  # excluded — they are workflow tooling, not security boundaries.
  protectedHomePaths = map (relative: "$HOME/.claude/hooks/${relative}") hookFiles ++ [
    "$HOME/.claude/settings.json"
    "$HOME/.claude/CLAUDE.md"
  ];

  # Each hook file is reachable through two routes — the symlinked view
  # under `$HOME/.claude/hooks/` and the real source in the dotfiles
  # checkout. `permissions.deny` accepts globs, so a `**/<repo>/...`
  # pattern covers the checkout without hardcoding its absolute location.
  # `sandbox.filesystem.denyWrite` is documented as literal paths only,
  # so the dotfiles route is intentionally omitted there.
  protectedDotfilesGlobs =
    map (relative: "**/${dotfilesName}/agents/hooks/${relative}") hookFiles
    ++ [ "**/${dotfilesName}/agents/AGENTS.md" ];

  permissionDenyPaths = protectedHomePaths ++ protectedDotfilesGlobs;

  protectedDenyPermissions =
    map (path: "Edit(${path})") permissionDenyPaths ++ map (path: "Write(${path})") permissionDenyPaths;

  generatedSettings = baseSettings // {
    permissions = baseSettings.permissions // {
      allow = nonBashPermissions baseSettings.permissions.allow ++ commandPolicy.claudeAllowPermissions;
      deny =
        nonBashPermissions baseSettings.permissions.deny
        ++ commandPolicy.claudeDenyPermissions
        ++ protectedDenyPermissions;
    };
    sandbox = baseSettings.sandbox // {
      filesystem = {
        denyWrite = protectedHomePaths;
      };
    };
  };
in
{
  inherit generatedSettings;

  generatedSettingsJson = builtins.toJSON generatedSettings;
}
