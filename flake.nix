{
  description =
    "factcheck: checks the claims a project's documentation makes against the repository it documents";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAll = f: nixpkgs.lib.genAttrs systems
        (system: f nixpkgs.legacyPackages.${system});
      pkg = pkgs: pkgs.stdenv.mkDerivation {
        name = "factcheck";
        src = self;
        nativeBuildInputs = [ pkgs.makeWrapper ];
        dontBuild = true;
        installPhase = ''
          mkdir -p $out/share/factcheck
          cp -r bin factcheck tests examples README.md LICENSE flake.nix \
            $out/share/factcheck/
          makeWrapper $out/share/factcheck/bin/factcheck $out/bin/factcheck \
            --prefix PATH : ${pkgs.python3}/bin
        '';
      };
    in
    {
      packages = forAll (pkgs: { default = pkg pkgs; });
    };
}
