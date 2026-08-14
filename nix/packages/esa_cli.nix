{
  lib,
  buildNpmPackage,
  fetchFromGitHub,
  nodejs_24,
  versionCheckHook,
}:

buildNpmPackage (finalAttrs: {
  pname = "esa-cli";
  version = "0.1.1";

  src = fetchFromGitHub {
    owner = "esaio";
    repo = "esa-cli";
    tag = "v${finalAttrs.version}";
    hash = "sha256-UZf9DvmjyxQ/95mbvemnuX/J9kcw8Wr3QBGOA4GdSlk=";
  };

  npmDepsHash = "sha256-ZuJeoQefkONTmPT8fIr5XucnwkTsOrEzou/yaoWS6/E=";
  nodejs = nodejs_24;
  npmBuildScript = "build";

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Official CLI for esa.io";
    homepage = "https://github.com/esaio/esa-cli";
    license = lib.licenses.mit;
    mainProgram = "esa";
  };
})
