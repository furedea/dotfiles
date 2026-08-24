{
  gitWt,
  installShellFiles,
}:

gitWt.overrideAttrs (previousAttrs: {
  nativeBuildInputs = (previousAttrs.nativeBuildInputs or [ ]) ++ [ installShellFiles ];

  postInstall = (previousAttrs.postInstall or "") + ''
    installShellCompletion --cmd git-wt \
      --bash <($out/bin/git-wt --init bash --nocd) \
      --fish <($out/bin/git-wt --init fish --nocd) \
      --zsh <($out/bin/git-wt --init zsh --nocd)
  '';
})
