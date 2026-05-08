_:

{
  overrides = {
    git-commit-split = {
      claude = {
        "argument-hint" = "{direct | pr-per-feature}";
      };
      codex = {
        "argument-hint" = "{direct | pr-per-feature}";
      };
    };

    report-doc-conflict = {
      claude = {
        "allowed-tools" = [
          "Bash"
          "Read"
          "Glob"
        ];
        "argument-hint" = "<description of the conflicting instructions>";
      };
      codex = {
        "argument-hint" = "<description of the conflicting instructions>";
      };
    };

    report-hook-block = {
      claude = {
        "allowed-tools" = [
          "Bash"
          "Read"
        ];
        "argument-hint" = "<what you were trying to do (optional)>";
      };
      codex = {
        "argument-hint" = "<what you were trying to do (optional)>";
      };
    };

    skill-auditor = {
      claude = {
        "disable-model-invocation" = true;
      };
    };
  };
}
