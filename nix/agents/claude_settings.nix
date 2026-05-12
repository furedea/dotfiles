{
  lib,
  username,
  dotfilesDir,
}:
let
  agentPaths = import ./paths.nix { inherit lib username dotfilesDir; };
  commandPolicy = import ./command_policy.nix { inherit lib; };
  agentHooks = import ./hooks.nix { };

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

  # Files Claude must never modify: the PreToolUse security harness plus
  # the configuration that binds it. Skill scripts are deliberately
  # excluded — they are workflow tooling, not security boundaries.
  protectedHomePaths = map (relative: "~/.claude/hooks/${relative}") hookFiles ++ [
    "~/.claude/rules/forbidden_commands.json"
    "~/.claude/settings.json"
    "~/.claude/CLAUDE.md"
  ];

  # Each hook file is reachable through two routes — the symlinked view
  # under `~/.claude/hooks/` and the real source in the dotfiles checkout.
  # Listing both literal `~/`-anchored paths keeps the rules username-free
  # and avoids relying on glob matching, which has been observed to miss
  # the absolute path the Edit/Write tool receives.
  protectedDotfilesPaths =
    map (relative: "${agentPaths.dotfilesHomePath}/agents/hooks/${relative}") hookFiles
    ++ [ "${agentPaths.dotfilesHomePath}/agents/AGENTS.md" ];

  protectedPaths = protectedHomePaths ++ protectedDotfilesPaths;

  protectedDenyPermissions =
    map (path: "Edit(${path})") protectedPaths ++ map (path: "Write(${path})") protectedPaths;

  generatedSettings = baseSettings // {
    hooks = agentHooks.claudeHooks;
    permissions = baseSettings.permissions // {
      allow = nonBashPermissions baseSettings.permissions.allow ++ commandPolicy.claudeAllowPermissions;
      deny =
        nonBashPermissions baseSettings.permissions.deny
        ++ commandPolicy.claudeDenyPermissions
        ++ protectedDenyPermissions;
    };
    sandbox = baseSettings.sandbox // {
      filesystem = (baseSettings.sandbox.filesystem or { }) // {
        denyWrite = protectedPaths;
      };
    };
  };
in
{
  inherit generatedSettings;

  generatedSettingsJson = builtins.toJSON generatedSettings;
}
