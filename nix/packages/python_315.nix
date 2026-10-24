{
  fetchurl,
  mailcap,
  python315,
}:

# nixpkgs ships 3.15.0, which has a certificate-handling vulnerability fixed in 3.15.1.
# Its mimetypes patch no longer applies to 3.15.1's restructured `knownfiles`, so the same
# substitution is done in postPatch instead.
(python315.override { mimetypesSupport = false; }).overrideAttrs (previousAttrs: rec {
  version = "3.15.1";
  src = fetchurl {
    url = "https://www.python.org/ftp/python/${version}/Python-${version}.tar.xz";
    hash = "sha256-ZzrnIy2EyJRymILIJX0wDvLSZSORG/05F+yM5/Um+Zs=";
  };

  postPatch = (previousAttrs.postPatch or "") + ''
    substituteInPlace Lib/mimetypes.py \
      --replace-fail '"/etc/mime.types",' '"${mailcap}/etc/mime.types",'
  '';
})
