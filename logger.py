#!/usr/bin/env python3
"""Keystroke logger using python-evdev. Captures keyboard events to JSONL."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import evdev
from evdev import ecodes


def find_keyboards() -> list[evdev.InputDevice]:
    """Find all keyboard devices."""
    keyboards = []
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        caps = device.capabilities()
        # Check if device has EV_KEY capability with typical keyboard keys
        if ecodes.EV_KEY in caps:
            keys = caps[ecodes.EV_KEY]
            # Look for letter keys (KEY_A through KEY_Z)
            if any(ecodes.KEY_A <= k <= ecodes.KEY_Z for k in keys):
                keyboards.append(device)
    return keyboards


def select_keyboard(keyboards: list[evdev.InputDevice]) -> evdev.InputDevice | None:
    """Let user select a keyboard if multiple found."""
    if not keyboards:
        return None
    if len(keyboards) == 1:
        return keyboards[0]

    print("Multiple keyboards found:")
    for i, kb in enumerate(keyboards):
        print(f"  {i}: {kb.name} ({kb.path})")

    try:
        choice = int(input("Select keyboard number: "))
        return keyboards[choice]
    except (ValueError, IndexError):
        return keyboards[0]


def log_events(device: evdev.InputDevice, output_path: Path, verbose: bool = False):
    """Log keyboard events to JSONL file."""
    print(f"Logging keystrokes from: {device.name}")
    print(f"Output file: {output_path}")
    print("Press Ctrl+C to stop\n")

    with open(output_path, "a") as f:
        try:
            for event in device.read_loop():
                if event.type != ecodes.EV_KEY:
                    continue

                # event.value: 0=release, 1=press, 2=hold/repeat
                event_type = {0: "release", 1: "press", 2: "repeat"}.get(event.value)
                if event_type is None:
                    continue

                key_name = ecodes.KEY.get(event.code, f"KEY_{event.code}")
                if isinstance(key_name, list):
                    key_name = key_name[0]

                record = {
                    "timestamp": event.timestamp(),
                    "datetime": datetime.fromtimestamp(event.timestamp()).isoformat(),
                    "code": event.code,
                    "key": key_name,
                    "event": event_type,
                }

                line = json.dumps(record)
                f.write(line + "\n")
                f.flush()

                if verbose:
                    print(f"{record['datetime']} {key_name:20} {event_type}")

        except KeyboardInterrupt:
            print("\nStopped logging.")


def main():
    parser = argparse.ArgumentParser(description="Log keyboard events to JSONL")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.home() / ".local/share/typing-analysis/keystrokes.jsonl",
        help="Output file path (default: ~/.local/share/typing-analysis/keystrokes.jsonl)"
    )
    parser.add_argument(
        "-d", "--device",
        type=str,
        help="Specific device path (e.g., /dev/input/event3)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print events to console"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available keyboards and exit"
    )
    args = parser.parse_args()

    keyboards = find_keyboards()

    if args.list:
        if not keyboards:
            print("No keyboards found. Do you have permission to read /dev/input/*?")
            sys.exit(1)
        print("Available keyboards:")
        for kb in keyboards:
            print(f"  {kb.path}: {kb.name}")
        sys.exit(0)

    if args.device:
        try:
            device = evdev.InputDevice(args.device)
        except (FileNotFoundError, PermissionError) as e:
            print(f"Error opening device {args.device}: {e}")
            sys.exit(1)
    else:
        device = select_keyboard(keyboards)
        if device is None:
            print("No keyboards found. Do you have permission to read /dev/input/*?")
            print("Try: sudo usermod -a -G input $USER  (then re-login)")
            sys.exit(1)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    log_events(device, args.output, args.verbose)


if __name__ == "__main__":
    main()
