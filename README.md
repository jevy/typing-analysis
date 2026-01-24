# Typing Analysis

Keystroke capture and analysis for Linux to improve typing skills. Captures at kernel level using python-evdev, runs as systemd service, and analyzes patterns for slow keys and error rates.

## Features

- **Keystroke Logger**: Captures keyboard events to JSONL format
- **Analyzer**: Calculates key frequency, digraph timing, error rates, and WPM
- **Report Generator**: CLI output showing areas for improvement

## Installation

### NixOS / Home Manager

Add to your flake or configuration:

```nix
{ pkgs, ... }:

let
  typing-analysis = pkgs.callPackage /path/to/typing-analysis/package.nix {};
in {
  # Add package
  home.packages = [ typing-analysis ];

  # Add user to input group to access /dev/input/*
  users.groups.input.members = [ "your-username" ];

  # Optional: Enable systemd service
  systemd.user.services.typing-logger = {
    Unit = {
      Description = "Typing Analysis Keystroke Logger";
      After = [ "graphical-session.target" ];
    };
    Service = {
      Type = "simple";
      ExecStart = "${typing-analysis}/bin/typing-log";
      Restart = "on-failure";
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
```

### Development

```bash
# Enter development shell
devenv shell

# Run tests
pytest -v

# Run logger manually (requires input group membership)
python logger.py --list           # List keyboards
python logger.py -v               # Log with verbose output
python logger.py -d /dev/input/event3  # Use specific device
```

## Usage

### Logging Keystrokes

```bash
# Start logger (runs in foreground)
typing-log

# Use specific device
typing-log -d /dev/input/event3

# Custom output file
typing-log -o ~/my-keystrokes.jsonl

# Verbose mode (prints each keystroke)
typing-log -v
```

### Analyzing Data

```bash
# Analyze all data
typing-analyze

# Output raw JSON
typing-analyze -o stats.json

# Filter by date range
typing-analyze --start 2025-01-01 --end 2025-01-31
```

### Generating Reports

```bash
# Full report
typing-report

# Today's stats only
typing-report --today

# Past week
typing-report --week

# JSON output
typing-report --json
```

## Report Output

```
============================================================
TYPING ANALYSIS REPORT
============================================================

Period: 2025-01-01 to 2025-01-24
Total duration: 168.5 hours

OVERALL STATISTICS
----------------------------------------
Total keystrokes: 125,432
Typing sessions: 847
Total typing time: 42.3 minutes
Average WPM: 72.4
Errors (backspaces): 3,421
Error rate: 2.7%

SLOWEST KEY TRANSITIONS (practice these)
----------------------------------------
  Q -> Z                     345ms
  X -> P                     298ms
  ...

KEYS BEFORE BACKSPACE (error-prone keys)
----------------------------------------
  E                          412 errors
  T                          387 errors
  ...
```

## Permissions

The logger needs read access to `/dev/input/*` devices. On NixOS:

```nix
users.groups.input.members = [ "your-username" ];
```

On other distros:

```bash
sudo usermod -a -G input $USER
# Then log out and back in
```

## Data Format

Keystrokes are stored as JSONL (one JSON object per line):

```json
{"timestamp": 1706123456.789, "datetime": "2025-01-24T12:34:56", "code": 30, "key": "KEY_A", "event": "press"}
{"timestamp": 1706123456.801, "datetime": "2025-01-24T12:34:56", "code": 30, "key": "KEY_A", "event": "release"}
```

Default location: `~/.local/share/typing-analysis/keystrokes.jsonl`

## License

MIT
