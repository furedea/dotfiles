# Custom overlays for packages not yet in nixpkgs.
# k1LoW/roots and k1LoW/git-wt are not packaged in nixpkgs (their PRs are
# pending upstream); pin to upstream releases and install shell completions.
[
  (final: _prev: {
    roots = final.buildGoModule rec {
      pname = "roots";
      version = "0.4.1";

      src = final.fetchFromGitHub {
        owner = "k1LoW";
        repo = "roots";
        rev = "v${version}";
        hash = "sha256-ACMRfWY/lhc3C/KVhuUyS1rgkSHGWPxZrmYt+pXupJI=";
      };

      vendorHash = "sha256-uxcT5VzlTCxxnx09p13mot0wVbbas/otoHdg7QSDt4E=";

      ldflags = [
        "-s"
        "-w"
        "-X github.com/k1LoW/roots/version.Version=${version}"
      ];

      nativeBuildInputs = [ final.installShellFiles ];

      postInstall = ''
        installShellCompletion --cmd roots \
          --bash <($out/bin/roots completion bash) \
          --fish <($out/bin/roots completion fish) \
          --zsh <($out/bin/roots completion zsh)
      '';

      meta = with final.lib; {
        description = "CLI for finding root directories in monorepo";
        homepage = "https://github.com/k1LoW/roots";
        license = licenses.mit;
        mainProgram = "roots";
      };
    };
  })

  (final: prev: {
    git-wt = prev.buildGo126Module (finalAttrs: {
      pname = "git-wt";
      version = "0.25.0";

      src = prev.fetchFromGitHub {
        owner = "k1LoW";
        repo = "git-wt";
        tag = "v${finalAttrs.version}";
        hash = "sha256-QdyONDVokpOaH5dI5v1rmaymCgIiWZ16h26FAIsAHPc=";
      };

      vendorHash = "sha256-O4vqouNxvA3GvrnpRO6GXDD8ysPfFCaaSJVFj2ufxwI=";

      nativeBuildInputs = [ prev.installShellFiles ];

      buildFlagsArray = [
        "-ldflags"
        "-X"
        "github.com/k1LoW/git-wt/version.Version=v${finalAttrs.version}"
      ];

      nativeCheckInputs = [ prev.git ];

      postInstall = ''
        installShellCompletion --cmd git-wt \
          --bash <($out/bin/git-wt --init bash --nocd) \
          --zsh <($out/bin/git-wt --init zsh --nocd) \
          --fish <($out/bin/git-wt --init fish --nocd)
      '';
    });
  })
]
