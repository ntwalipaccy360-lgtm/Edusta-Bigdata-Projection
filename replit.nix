{pkgs}: {
  deps = [
    pkgs.gcc-unwrapped
    pkgs.gobject-introspection
    pkgs.pkg-config
    pkgs.cairo
  ];
}
