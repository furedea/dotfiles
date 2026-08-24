# Custom overlays for packages not yet in nixpkgs.
# Pin ical, xurl, k1LoW/roots, and k1LoW/git-wt to upstream releases and
# install their shell completions.
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

    xurl = final.stdenvNoCC.mkDerivation rec {
      pname = "xurl";
      version = "1.3.1";

      src = final.fetchurl {
        url = "https://github.com/xdevplatform/xurl/releases/download/v${version}/xurl_Darwin_arm64.tar.gz";
        hash = "sha256-XhJwfLTsYl/0TPbiJ4Dq455DD6E9tuiQxD20Lb6voAg=";
      };

      sourceRoot = ".";

      nativeBuildInputs = [ final.installShellFiles ];

      installPhase = ''
        runHook preInstall

        install -Dm755 xurl "$out/bin/xurl"
        install -Dm644 LICENSE "$out/share/licenses/xurl/LICENSE"
        installShellCompletion --cmd xurl \
          --bash <($out/bin/xurl completion bash) \
          --fish <($out/bin/xurl completion fish) \
          --zsh <($out/bin/xurl completion zsh)

        runHook postInstall
      '';

      dontStrip = true;

      meta = with final.lib; {
        description = "Auth-enabled curl-like CLI for the X API";
        homepage = "https://github.com/xdevplatform/xurl";
        license = licenses.mit;
        mainProgram = "xurl";
        platforms = [ "aarch64-darwin" ];
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
