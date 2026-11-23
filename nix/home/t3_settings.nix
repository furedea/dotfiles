# T3 Code writes these files from its UI, so activation merges only the chosen keys
# into them instead of linking them (ADR-0046). A managed key changed in the UI returns
# to this value at the next switch; every other key stays as the UI left it.
{
  pkgs,
  lib,
  enableT3Service,
  ...
}:
let
  mergeSettings = pkgs.writeShellScript "merge_t3_settings" ''
    export JQ_BIN=${lib.getExe pkgs.jq}
    ${builtins.readFile ../../scripts/t3/merge_settings.sh}
  '';
  # Deep merge: nested objects such as storageCleanup keep their unmanaged keys.
  mergeObject = "(. // {}) * $managed";
  # Exactly one thread.stop rule: drop the others so a key rebound in the UI returns.
  replaceStopRule = ''[(. // [])[] | select(.command != "thread.stop")] + [$managed]'';

  stopRule = {
    key = "ctrl+c";
    command = "thread.stop";
    when = "turnRunning && !terminalFocus";
  };
  # The desktop app's own settings, read when its window opens.
  clientSettings = {
    notificationMode = "notifications-and-sound";
    inAppNotificationsEnabled = true;
    confirmThreadUnpin = true;
    confirmThreadArchive = true;
    confirmThreadDelete = true;
    confirmQuit = "double-click";
    language = "ja";
    threadDetailsItems = {
      openIn = false;
      scripts = false;
      servers = false;
      automations = false;
      usage = true;
      context = true;
    };
    fontFamilyCode = "JetBrains Mono";
    mathRenderingEnabled = true;
    composerRichTextEnabled = false;
    diffLayout = "split";
    browserAutoShowFloatingPreview = false;
  };
  # The server's settings, applied to every thread it runs; it reloads the file on change.
  serverSettings = {
    enableAgentBrowserAccess = false;
    defaultAutoPull = true;
    defaultModelSelection = {
      instanceId = "claudeAgent";
      model = "claude-opus-5-5";
      options = [
        {
          id = "effort";
          value = "medium";
        }
      ];
    };
    fallbackModelSelection = {
      instanceId = "codex";
      model = "gpt-6.2-sol";
      options = [
        {
          id = "reasoningEffort";
          value = "medium";
        }
      ];
    };
    defaultRuntimeMode = "auto";
    snoozeLimitedThreads = true;
    autoResumeLimitedThreads = true;
    addProjectBaseDirectory = "~/ghq";
    ghqCloneLayout = true;
    removeAgentCreditsOnMerge = true;
    pullRequestMergeMethod = "squash";
    storageCleanup = {
      worktreeOnMerge = true;
      worktreeOnDelete = true;
    };
  };
  # The launchd server owns ~/.t3 only while the desktop app runs as a client (ADR-0045).
  desktopSettings.localEnvironmentEnabled = false;

  # A file the merge cannot parse stays unchanged and does not stop the rest of the switch.
  merge = file: filter: value: ''
    run ${mergeSettings} "$t3Userdata/${file}" ${lib.escapeShellArg filter} ${lib.escapeShellArg (builtins.toJSON value)} \
      || echo "t3: left ${file} unchanged (could not merge the managed settings)" >&2
  '';
in
{
  home.activation.t3Settings = lib.hm.dag.entryAfter [ "writeBoundary" ] (
    lib.concatStrings (
      [
        ''
          t3Userdata="$HOME/.t3/userdata"
        ''
        (merge "keybindings.json" replaceStopRule stopRule)
        (merge "client-settings.json" mergeObject clientSettings)
      ]
      ++ lib.optionals enableT3Service [
        (merge "settings.json" mergeObject serverSettings)
        (merge "desktop-settings.json" mergeObject desktopSettings)
      ]
    )
  );
}
