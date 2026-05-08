{ lib }:
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

  # Files Claude must never modify: the PreToolUse security harness plus
  # the configuration that binds it. Skill scripts are deliberately
  # excluded — they are workflow tooling, not security boundaries.
  protectedHomePaths =
    map (relative: "$HOME/.claude/hooks/${relative}") (filesUnder ../../agents/hooks)
    ++ [
      "$HOME/.claude/settings.json"
      "$HOME/.claude/CLAUDE.md"
    ];

  protectedDenyPermissions =
    map (path: "Edit(${path})") protectedHomePaths ++ map (path: "Write(${path})") protectedHomePaths;

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
