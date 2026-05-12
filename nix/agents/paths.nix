{
  lib,
  username,
  dotfilesDir,
}:
let
  dotfilesHomePath = "~/" + lib.removePrefix "/Users/${username}/" dotfilesDir;
in
{
  inherit dotfilesHomePath;
}
