{
  fetchurl,
  mailcap,
  python315,
}:

# Drop once the nixpkgs input ships >= 3.15.2, the first release whose `ssl` module denylists
# the compromised eMudhra intermediates (nixpkgs ships 3.15.0).
# The nixpkgs mimetypes patch no longer applies to the restructured `knownfiles`, so the same
# substitution is done in postPatch instead.
(python315.override { mimetypesSupport = false; }).overrideAttrs (previousAttrs: rec {
  version = "3.15.2";
  src = fetchurl {
    url = "https://www.python.org/ftp/python/${version}/Python-${version}.tar.xz";
    hash = "sha256-i1U20oAULs9s3+FdEqIbocZeMAu/eyio0M24SVdXl94=";
  };

  postPatch = (previousAttrs.postPatch or "") + ''
    substituteInPlace Lib/mimetypes.py \
      --replace-fail '"/etc/mime.types",' '"${mailcap}/etc/mime.types",'
  '';
})
