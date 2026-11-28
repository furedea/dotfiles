# The Herdr desktop app writes its settings file itself, so activation merges only the managed
# keys into it instead of linking it. The app reports anonymous usage daily unless the file says
# "telemetry": false; the DO_NOT_TRACK and HERDR_TELEMETRY variables do not reach an app started
# from the Dock.
{
  pkgs,
  lib,
  ...
}:
let
  # The merge command is the generic one that the T3 settings use, too.
  mergeSettings = pkgs.writeShellScript "merge_herdr_app_settings" ''
    export JQ_BIN=${lib.getExe pkgs.jq}
    ${builtins.readFile ../../scripts/t3/merge_settings.sh}
  '';
  settingsFile = "$HOME/.config/herdr-app/settings.json";
  managedSettings = {
    telemetry = false;
  };
in
{
  # A file the merge cannot parse stays unchanged and does not stop the rest of the switch.
  home.activation.herdrAppSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    run ${mergeSettings} "${settingsFile}" '(. // {}) * $managed' ${lib.escapeShellArg (builtins.toJSON managedSettings)} \
      || echo "herdr-app: left settings.json unchanged (could not merge the managed settings)" >&2
  '';
}
