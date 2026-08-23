{
  description = "Jibo modding toolkit on NixOS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};


        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          # Added because we don't want JiboModTool.py nagging us :D
          packaging
          paramiko # From requirements.txt 
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          name = "jibo-mod-shell";

          buildInputs = with pkgs; [
            gcc
            gnumake
            git
            libusb1 # includes libusb-1.0
            usbutils # includes lsusb
            e2fsprogs # includes debugfs
            pythonEnv
            python3Packages.pip
            gcc-arm-embedded # For compiling shofel
          ];

          shellHook = ''
            echo "  JiboAutoMod is ready for nix."
          '';
        };
      });
}
