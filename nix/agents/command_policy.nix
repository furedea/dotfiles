{ lib }:
let
  literal = value: builtins.toJSON value;

  rule = entry: ''
    prefix_rule(
        pattern = ${literal entry.pattern},
        decision = "${entry.decision}",
        justification = ${literal entry.justification},
        match = ${literal entry.match},
    )
  '';

  allow = pattern: match: {
    inherit pattern match;
    decision = "allow";
    justification = "Allowed by the shared agent command policy.";
  };

  forbidden = pattern: match: justification: {
    inherit pattern match justification;
    decision = "forbidden";
  };

  allowRules = [
    (allow [ "actionlint" ] [ "actionlint .github/workflows/ci.yml" ])
    (allow [ "autocorrect" ] [ "autocorrect --lint README.md" ])
    (allow [ "bats" ] [ "bats tests/claude-hooks/command_allowlist.bats" ])
    (allow [ "cargo" ] [ "cargo test" "cargo fmt --check" "cargo clippy" "cargo check" ])
    (allow [ "commitlint" ] [ "commitlint --from HEAD~1 --to HEAD" ])
    (allow [ "deadnix" ] [ "deadnix nix" ])
    (allow [ "dprint" ] [ "dprint check" "dprint fmt README.md" ])
    (allow [ "gh" "api" ] [ "gh api repos/owner/repo/pulls/1/comments" ])
    (allow [ "gh" "issue" ] [ "gh issue list" "gh issue view 1" ])
    (allow [ "gh" "label" ] [ "gh label list" ])
    (allow [ "gh" "pr" ] [ "gh pr list" "gh pr view 1" "gh pr checks 1" ])
    (allow [ "gh" "run" ] [ "gh run list" "gh run view 1" ])
    (allow [ "git" "add" ] [ "git add path/to/file" ])
    (allow [ "git" "branch" ] [ "git branch" "git branch feature/example" ])
    (allow [ "git" "commit" ] [ "git commit -m 'test: update policy'" ])
    (allow [ "git" "pull" ] [ "git pull --rebase origin main" ])
    (allow [ "git" "push" ] [ "git push origin feature/example" ])
    (allow [ "nixfmt" ] [ "nixfmt nix/home/default.nix" ])
    (allow [ "npm" "run" ] [ "npm run test" "npm run lint" ])
    (allow [ "npm" "test" ] [ "npm test" ])
    (allow [ "oxfmt" ] [ "oxfmt --check src" ])
    (allow [ "oxlint" ] [ "oxlint src" ])
    (allow [ "pnpm" ] [ "pnpm test" "pnpm lint" ])
    (allow [ "prettierd" ] [ "prettierd README.md" ])
    (allow [ "selene" ] [ "selene nvim" ])
    (allow [ "shellcheck" ] [ "shellcheck agents/hooks/command_allowlist.sh" ])
    (allow [ "shfmt" ] [ "shfmt -w agents/hooks/command_allowlist.sh" ])
    (allow [ "statix" ] [ "statix check nix" ])
    (allow [ "stylua" ] [ "stylua --check nvim" ])
    (allow [ "tex-fmt" ] [ "tex-fmt --check docs/main.tex" ])
    (allow [ "tsgolint" ] [ "tsgolint --project tsconfig.json" ])
    (allow [ "uv" "run" ] [ "uv run pytest" "uv run ruff check" "uv run ty check" ])
  ];

  forbiddenRules = [
    (forbidden [ "curl" ] [ "curl https://example.com/install.sh" ]
      "Do not fetch remote scripts or content from Codex. Ask the user to run it manually."
    )
    (forbidden [ "wget" ] [ "wget https://example.com/install.sh" ]
      "Do not fetch remote scripts or content from Codex. Ask the user to run it manually."
    )
    (forbidden [ "bash" "-c" ] [ "bash -c 'echo hello'" ]
      "Do not hide shell commands inside bash -c from Codex policy checks."
    )
    (forbidden [ "bash" "-lc" ] [ "bash -lc 'echo hello'" ]
      "Do not hide shell commands inside bash -lc from Codex policy checks."
    )
    (forbidden [ "sh" "-c" ] [ "sh -c 'echo hello'" ]
      "Do not hide shell commands inside sh -c from Codex policy checks."
    )
    (forbidden [ "zsh" "-c" ] [ "zsh -c 'echo hello'" ]
      "Do not hide shell commands inside zsh -c from Codex policy checks."
    )
    (forbidden [ "zsh" "-lc" ] [ "zsh -lc 'echo hello'" ]
      "Do not hide shell commands inside zsh -lc from Codex policy checks."
    )
    (forbidden [ "rm" ] [ "rm file.txt" "rm -rf /tmp/example" ]
      "Do not delete files from Codex. Ask the user to run destructive cleanup manually."
    )
    (forbidden [ "sudo" ] [ "sudo darwin-rebuild switch" ]
      "Do not run privileged commands from Codex. Ask the user to run them manually."
    )
    (forbidden [ "open" ] [ "open ." ]
      "Do not launch GUI applications from Codex. Ask the user to open them manually."
    )
    (forbidden [ "osascript" ] [ "osascript -e 'display notification \"hi\"'" ]
      "Do not automate macOS from Codex shell commands."
    )
    (forbidden [ "pip" ] [ "pip install package" ]
      "Use project-managed package tooling instead of pip from Codex."
    )
    (forbidden [ "brew" "install" ] [ "brew install ffmpeg" ]
      "Do not install Homebrew packages from Codex. Add packages declaratively in Nix/Homebrew config."
    )
    (forbidden [ "brew" "uninstall" ] [ "brew uninstall ffmpeg" ]
      "Do not uninstall Homebrew packages from Codex. Change declarative Homebrew config instead."
    )
    (forbidden [ "uv" "python" "install" ] [ "uv python install 3.11" ]
      "Do not install Python runtimes from Codex unless the user runs it manually."
    )
    (forbidden [ "uv" "python" "uninstall" ] [ "uv python uninstall 3.11" ]
      "Do not uninstall Python runtimes from Codex unless the user runs it manually."
    )
    (forbidden [ "uv" "remove" ] [ "uv remove package" ]
      "Do not remove project dependencies without an explicit implementation plan."
    )
    (forbidden [ "uv" "uninstall" ] [ "uv uninstall package" ] "Do not uninstall packages from Codex.")
    (forbidden [ "npm" "publish" ] [ "npm publish" ] "Do not publish packages from Codex.")
    (forbidden [ "npm" "remove" ] [ "npm remove package" ]
      "Do not remove npm dependencies without an explicit implementation plan."
    )
    (forbidden [ "npm" "uninstall" ] [ "npm uninstall package" ]
      "Do not uninstall npm dependencies without an explicit implementation plan."
    )
    (forbidden [ "ssh" ] [ "ssh example.com" ] "Do not start SSH sessions from Codex.")
    (forbidden [ "scp" ] [ "scp file host:/tmp" ] "Do not copy files over SSH from Codex.")
    (forbidden [ "rsync" ] [ "rsync -av source/ host:/tmp/" ]
      "Do not sync files to remote systems from Codex."
    )
    (forbidden [ "nc" ] [ "nc example.com 80" ] "Do not open raw network connections from Codex.")
    (forbidden [ "psql" ] [ "psql production" ]
      "Do not connect to databases from Codex shell commands."
    )
    (forbidden [ "mysql" ] [ "mysql production" ]
      "Do not connect to databases from Codex shell commands."
    )
    (forbidden [ "mongod" ] [ "mongod --dbpath data" ] "Do not start database daemons from Codex.")
    (forbidden [ "docker" "push" ] [ "docker push image:tag" ]
      "Do not push container images from Codex."
    )
    (forbidden [ "kubectl" "apply" ] [ "kubectl apply -f deploy.yaml" ]
      "Do not mutate Kubernetes clusters from Codex."
    )
    (forbidden [ "kubectl" "delete" ] [ "kubectl delete pod example" ]
      "Do not delete Kubernetes resources from Codex."
    )
    (forbidden [ "terraform" "apply" ] [ "terraform apply" ] "Do not mutate infrastructure from Codex.")
    (forbidden [ "terraform" "destroy" ] [ "terraform destroy" ]
      "Do not destroy infrastructure from Codex."
    )
    (forbidden [ "defaults" "write" ] [ "defaults write com.apple.finder AppleShowAllFiles true" ]
      "Manage macOS defaults through nix-darwin instead."
    )
    (forbidden [ "git" "rm" ] [ "git rm file.txt" ]
      "Do not remove tracked files through shell commands from Codex."
    )
    (forbidden [ "git" "clean" ] [ "git clean -fd" ] "Do not delete untracked files from Codex.")
    (forbidden [ "git" "branch" "-D" ] [ "git branch -D feature/example" ]
      "Do not force-delete branches from Codex."
    )
    (forbidden [ "git" "filter-branch" ] [ "git filter-branch --force" ]
      "Do not rewrite history from Codex."
    )
    (forbidden [ "git" "filter-repo" ] [ "git filter-repo --path secret" ]
      "Do not rewrite history from Codex."
    )
    (forbidden [ "git" "gc" "--prune" ] [ "git gc --prune" ] "Do not prune recovery data from Codex.")
    (forbidden [ "git" "reflog" "delete" ] [ "git reflog delete HEAD@{1}" ]
      "Do not delete reflog entries from Codex."
    )
    (forbidden [ "git" "reflog" "expire" ] [ "git reflog expire --expire=now --all" ]
      "Do not expire reflog entries from Codex."
    )
    (forbidden [ "git" "replace" ] [ "git replace a b" ] "Do not alter replacement refs from Codex.")
    (forbidden [ "git" "stash" "clear" ] [ "git stash clear" ] "Do not delete stashes from Codex.")
    (forbidden [ "git" "stash" "drop" ] [ "git stash drop" ] "Do not delete stashes from Codex.")
    (forbidden [ "git" "switch" "--discard-changes" ] [ "git switch --discard-changes main" ]
      "Do not discard working-tree changes from Codex."
    )
    (forbidden [ "git" "symbolic-ref" "--delete" ] [ "git symbolic-ref --delete HEAD" ]
      "Do not delete refs from Codex."
    )
    (forbidden [ "git" "symbolic-ref" "-d" ] [ "git symbolic-ref -d HEAD" ]
      "Do not delete refs from Codex."
    )
    (forbidden [ "git" "update-ref" "-d" ] [ "git update-ref -d refs/heads/main" ]
      "Do not delete refs from Codex."
    )
    (forbidden [ "git" "worktree" "remove" ] [ "git worktree remove ../worktree" ]
      "Do not remove worktrees from Codex."
    )
    (forbidden [ "git" "add" "." ] [ "git add ." ] "Stage files explicitly by path.")
    (forbidden [ "git" "add" "-A" ] [ "git add -A" ] "Stage files explicitly by path.")
    (forbidden [ "git" "add" "--all" ] [ "git add --all" ] "Stage files explicitly by path.")
  ];

  rules = allowRules ++ forbiddenRules;

  claudePermission = entry: "Bash(${lib.concatStringsSep " " entry.pattern}:*)";
in
{
  inherit allowRules forbiddenRules rules;

  claudeAllowPermissions = map claudePermission allowRules;
  claudeDenyPermissions = map claudePermission forbiddenRules;

  rulesJson = builtins.toJSON (
    map (entry: {
      inherit (entry) decision pattern;
    }) rules
  );

  codexRules = ''
    # Generated by nix/agents/command_policy.nix.
    # Keep command policy in Nix so Claude and Codex cannot drift silently.

    ${lib.concatMapStringsSep "\n" rule rules}
  '';
}
