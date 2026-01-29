# Typing Analysis

A background keystroke logger and analyzer for Linux to help improve typing skills.

## Architecture

Three CLI tools, all Python:

- **`typing-log`** (`logger.py`) - Captures keystrokes via evdev from `/dev/input/*` devices. Runs as a systemd user service, writes JSONL to `~/.local/share/typing-analysis/keystrokes.jsonl`
- **`typing-analyze`** (`analyze.py`) - Processes JSONL into statistics (WPM, error rates, digraph timings). Returns JSON.
- **`typing-report`** (`report.py`) - Human-readable report from analyze output. Shows slowest transitions, error-prone keys, etc.

## Data Format

Each keystroke is a JSONL line:
```json
{"timestamp": 1706123456.789, "datetime": "2026-01-24T12:34:56", "code": 30, "key": "KEY_A", "event": "press"}
```

Events: `press`, `release`, `repeat`

## NixOS Integration

- `flake.nix` - Exports package and `homeManagerModules.default`
- `module.nix` - Home-manager module with `services.typing-analysis.enable`
- `package.nix` - Python package definition

Enable in home-manager:
```nix
imports = [ typing-analysis.homeManagerModules.default ];
services.typing-analysis.enable = true;
```

User must be in `input` group (set in NixOS config, not home-manager).

## Key Behaviors

**Device selection**: When multiple keyboards exist, auto-selects first one in non-interactive mode (systemd). Interactive mode prompts user.

**Kanata compatibility**: If user has kanata for homerow mods, the logger captures from the kanata virtual keyboard (processed output), not the raw physical keyboard.

**Error detection**: Backspaces are counted as errors. Keys pressed immediately before backspace are flagged as error-prone.

**Session detection**: Gaps > 5 minutes between keystrokes start a new typing session.

## Analysis Metrics

- **WPM**: Words per minute (characters / 5 / minutes)
- **Error rate**: Backspaces / total keystrokes
- **Digraph timing**: Time between consecutive key presses
- **Slowest transitions**: Key pairs that take longest (practice targets)
- **Error-prone keys**: Keys most often followed by backspace

## Development

```bash
nix develop  # or: devenv shell
pytest       # run tests
```

## Typing Experiments

The user tracks typing improvement experiments in `~/typing-experiments.md`. This file logs:
- Baseline metrics before config changes
- Kanata config changes (tap-time, hold-time, tap-hold strategies)
- Results after changes (error rate, homerow mod failures)
- Subjective feel and verdict

**After making kanata config changes**, run `typing-report` to gather new metrics and update `~/typing-experiments.md` with the results.

## Kanata Configuration

Kanata homerow mod config is in: `/home/jevin/.config/nixpkgs/nixos/configuration.nix`

Key settings to look for:
- `tap-time` - How long before a key becomes a hold (default 150-200ms)
- `hold-time` - How long to hold for modifier activation
- `tap-hold-release-keys` - Achordion-style same-hand key lists

## Common Issues

- **Permission denied on /dev/input/***: User not in `input` group
- **Service not starting**: Check `journalctl --user -u typing-logger`
- **No data**: Service may have selected wrong keyboard, check with `typing-log --list`
