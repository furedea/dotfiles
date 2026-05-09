_:

let
  # Codex disables auto-trigger only via `<skill>/agents/openai.yaml` with
  # `policy.allow_implicit_invocation: false`. There is no equivalent
  # frontmatter flag, no `~/.codex/config.toml` toggle that preserves explicit
  # invocation, and `~/.codex/prompts/` is deprecated. Source:
  # codex-rs/core-skills/src/loader.rs (SKILLS_METADATA_FILENAME = "openai.yaml")
  # codex-rs/core-skills/src/model.rs (allow_implicit_invocation default true).
  codexExplicitOnly = ''
    policy:
      allow_implicit_invocation: false
  '';

  # Pair both providers' explicit-only flags so a "command-style skill" stays
  # symmetric across Claude and Codex.
  explicitOnly = {
    frontmatter.claude."disable-model-invocation" = true;
    files.codex."agents/openai.yaml" = codexExplicitOnly;
  };
in

{
  overrides = {
    git-commit-split = {
      frontmatter.claude = {
        "disable-model-invocation" = true;
        "argument-hint" = "{direct | pr-per-feature}";
      };
      frontmatter.codex."argument-hint" = "{direct | pr-per-feature}";
      files.codex."agents/openai.yaml" = codexExplicitOnly;
    };

    github-ci-init = explicitOnly;

    nix-dev-init = explicitOnly;

    skill-auditor = {
      frontmatter.claude."disable-model-invocation" = true;
      files.codex."agents/openai.yaml" = codexExplicitOnly;
    };
  };
}
