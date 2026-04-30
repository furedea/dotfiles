{ lib }:
let
  commandPolicy = import ./command_policy.nix { inherit lib; };

  baseSettings = builtins.fromJSON (builtins.readFile ../../claude/settings.base.json);

  isBashPermission = permission: lib.hasPrefix "Bash(" permission;

  nonBashPermissions =
    permissions: builtins.filter (permission: !(isBashPermission permission)) permissions;

  generatedSettings = baseSettings // {
    permissions = baseSettings.permissions // {
      allow = nonBashPermissions baseSettings.permissions.allow ++ commandPolicy.claudeAllowPermissions;
      deny = nonBashPermissions baseSettings.permissions.deny ++ commandPolicy.claudeDenyPermissions;
    };
  };
in
{
  inherit generatedSettings;

  generatedSettingsJson = builtins.toJSON generatedSettings;
}
