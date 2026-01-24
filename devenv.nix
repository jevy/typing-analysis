{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.evtest  # For testing input devices
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    package = pkgs.python313.withPackages (ps: [
      ps.evdev
      ps.pytest
    ]);
  };

  # https://devenv.sh/processes/
  # processes.dev.exec = "${lib.getExe pkgs.watchexec} -n -- ls -la";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.typing-log.exec = ''
    python logger.py "$@"
  '';
  scripts.typing-analyze.exec = ''
    python analyze.py "$@"
  '';
  scripts.typing-report.exec = ''
    python report.py "$@"
  '';

  # https://devenv.sh/basics/
  enterShell = ''
    echo "Typing Analysis Dev Environment"
    echo "Commands: typing-log, typing-analyze, typing-report"
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    pytest -v
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
