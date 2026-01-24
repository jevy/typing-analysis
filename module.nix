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
      description = "Specific input device path (e.g., /dev/input/event3). Auto-detects if null.";
    };

    logPath = lib.mkOption {
      type = lib.types.str;
      default = "$HOME/.local/share/typing-analysis/keystrokes.jsonl";
      description = "Path to store keystroke logs.";
    };
  };

  config = lib.mkIf cfg.enable {
    # Add user to input group to read /dev/input/*
    users.groups.input.members = [ config.users.users.${config.home.username}.name ];

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
