# Custom overlays for packages not yet in nixpkgs.
# Pin ical, k1LoW/roots, and k1LoW/git-wt to upstream releases and install
# their shell completions.
[
  (final: _prev: {
    ical = final.buildGoModule rec {
      pname = "ical";
      version = "0.12.2";

      src = final.fetchFromGitHub {
        owner = "BRO3886";
        repo = "ical";
        rev = "v${version}";
        hash = "sha256-APmqU3yqiA08RH/5ED220Q3yZIQ2zFURbDEsf0xpt38=";
      };

      vendorHash = "sha256-an2RZmzdfL2wz3tE/4w1hGTmihaai0C33E9R/tMAa5c=";

      subPackages = [ "cmd/ical" ];

      env.CGO_ENABLED = 1;

      ldflags = [
        "-s"
        "-w"
        "-X main.version=v${version}"
        "-X main.commit=${src.rev}"
        "-X main.date=1970-01-01T00:00:00Z"
      ];

      nativeBuildInputs = [ final.installShellFiles ];

      postInstall = ''
        installShellCompletion --cmd ical \
          --bash <($out/bin/ical completion bash) \
          --fish <($out/bin/ical completion fish) \
          --zsh <($out/bin/ical completion zsh)
      '';

      meta = with final.lib; {
        description = "Native CLI for Apple Calendar using EventKit";
        homepage = "https://ical.sidv.dev";
        license = licenses.mit;
        mainProgram = "ical";
        platforms = platforms.darwin;
      };
    };

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

  (_: prev: {
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
