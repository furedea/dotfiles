{
  lib,
  username,
  dotfilesDir,
}:
let
  agentPaths = import ./paths.nix { inherit lib username dotfilesDir; };

  filesUnder =
    root:
    let
      prefix = toString root + "/";
    in
    map (path: lib.removePrefix prefix (toString path)) (lib.filesystem.listFilesRecursive root);

  agentHookFiles = filesUnder ../../agents/hooks;
  codexHookFiles = filesUnder ../../codex/hooks;

  # Codex's `[permissions.<profile>.filesystem]` is the symmetric counterpart
  # to Claude's `permissions.deny: Edit/Write` plus `sandbox.filesystem.denyWrite`:
  # it applies uniformly to Edit / Write / apply_patch / shell I/O, so a single
  # `"read"` entry blocks every write path. Listing each file (rather than the
  # parent directory) preserves the ability to create new sibling files.
  protectedHomePaths =
    map (relative: "~/.claude/hooks/${relative}") agentHookFiles
    ++ map (relative: "~/.codex/hooks/${relative}") codexHookFiles
    ++ [
      "~/.claude/CLAUDE.md"
      "~/.claude/rules/forbidden_commands.json"
      "~/.claude/settings.json"
      "~/.codex/AGENTS.md"
      "~/.codex/hooks.json"
      "~/.codex/rules/default.rules"
    ];

  # Earlier revisions used `/**/<repo>/...` globs here to stay independent
  # of where the dotfiles checkout lived, but Claude Code's permission
  # evaluator was observed not to match those globs against the absolute
  # path the Edit/Write tool receives. Listing the literal `~/`-anchored
  # paths is username-free yet bypasses the glob behavior entirely.
  protectedDotfilesPaths =
    map (relative: "${agentPaths.dotfilesHomePath}/agents/hooks/${relative}") agentHookFiles
    ++ map (relative: "${agentPaths.dotfilesHomePath}/codex/hooks/${relative}") codexHookFiles
    ++ [
      "${agentPaths.dotfilesHomePath}/agents/AGENTS.md"
    ];

  protectedPaths = protectedHomePaths ++ protectedDotfilesPaths;

  pathEntries = lib.listToAttrs (
    map (path: {
      name = path;
      value = "read";
    }) protectedPaths
  );

  globScanMaxDepth = 5;

  filesystemPermissions = pathEntries // {
    glob_scan_max_depth = globScanMaxDepth;
  };

  # Hand-written TOML so this module stays pure-`lib` (no `pkgs.formats.toml`,
  # no import-from-derivation). The output is consumed both by the home-manager
  # activation (concatenated with `codex/config.toml`) and by tests via
  # `lib.codexConfigFragmentToml`.
  tomlEscape = value: builtins.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ] value;
  pathLine = path: ''"${tomlEscape path}" = "read"'';

  # `default_permissions = "guarded"` is intentionally NOT emitted. Codex
  # treats a selected permissions profile as the full filesystem sandbox
  # policy, so this narrow file list would otherwise prevent read-only shell
  # commands from starting. Hooks remain the default harness boundary; this
  # profile is available for explicit experiments only.
  configFragmentToml = ''
    [permissions.guarded.filesystem]
    ${lib.concatMapStringsSep "\n" pathLine protectedPaths}
    glob_scan_max_depth = ${toString globScanMaxDepth}
  '';
in
{
  inherit filesystemPermissions configFragmentToml;
}
