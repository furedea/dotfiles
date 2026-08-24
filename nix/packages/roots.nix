{
  buildGoModule,
  fetchFromGitHub,
  installShellFiles,
  lib,
  versionCheckHook,
}:

buildGoModule (finalAttrs: {
  pname = "roots";
  version = "0.4.1";

  src = fetchFromGitHub {
    owner = "k1LoW";
    repo = "roots";
    tag = "v${finalAttrs.version}";
    hash = "sha256-ACMRfWY/lhc3C/KVhuUyS1rgkSHGWPxZrmYt+pXupJI=";
  };

  vendorHash = "sha256-uxcT5VzlTCxxnx09p13mot0wVbbas/otoHdg7QSDt4E=";

  ldflags = [
    "-s"
    "-w"
    "-X github.com/k1LoW/roots/version.Version=${finalAttrs.version}"
  ];

  nativeBuildInputs = [ installShellFiles ];

  postInstall = ''
    installShellCompletion --cmd roots \
      --bash <($out/bin/roots completion bash) \
      --fish <($out/bin/roots completion fish) \
      --zsh <($out/bin/roots completion zsh)
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "CLI for finding root directories in monorepo";
    homepage = "https://github.com/k1LoW/roots";
    license = lib.licenses.mit;
    mainProgram = "roots";
  };
})
