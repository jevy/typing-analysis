{ config, lib, pkgs, ... }:

let
  cfg = config.services.typing-analysis;
  typing-analysis = pkgs.callPackage ./package.nix {};
in {
  options.services.typing-analysis = {
    enable = lib.mkEnableOption "Typing Analysis keystroke logger";

    device = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Specific input device path (e.g., /dev/input/event3). Auto-selects first keyboard if null.";
    };

    logPath = lib.mkOption {
      type = lib.types.str;
      default = "%h/.local/share/typing-analysis/keystrokes.jsonl";
      description = "Path to store keystroke logs. %h expands to home directory.";
    };
  };

  config = lib.mkIf cfg.enable {
    # NOTE: User must be in 'input' group. Add to NixOS config:
    # users.users.yourname.extraGroups = [ "input" ];
    # Or: users.groups.input.members = [ "yourname" ];

    home.packages = [ typing-analysis ];

    systemd.user.services.typing-logger = {
      Unit = {
        Description = "Typing Analysis Keystroke Logger";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };

      Service = {
        Type = "simple";
        ExecStart =
          let
            deviceArg = lib.optionalString (cfg.device != null) "-d ${cfg.device}";
          in
            "${typing-analysis}/bin/typing-log ${deviceArg} -o ${cfg.logPath}";
        Restart = "on-failure";
        RestartSec = 10;
      };

      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };
  };
}
