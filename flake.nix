{
  description = "Keystroke capture and analysis for improving typing skills";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in {
          default = pkgs.callPackage ./package.nix {};
          typing-analysis = pkgs.callPackage ./package.nix {};
        }
      );

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python313.withPackages (ps: [ ps.evdev ps.pytest ]))
              pkgs.evtest
            ];
          };
        }
      );
    };
}
