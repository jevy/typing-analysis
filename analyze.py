#!/usr/bin/env python3
"""Analyze keystroke data from JSONL logs."""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class TypingSession:
    """A continuous typing session (gap < threshold)."""
    start: float
    end: float
    keystrokes: int
    chars: int  # Approximate character count


@dataclass
class AnalysisResult:
    """Results from analyzing keystroke data."""
    total_keystrokes: int = 0
    total_press_events: int = 0
    key_frequency: Counter = field(default_factory=Counter)
    digraph_times: dict = field(default_factory=lambda: defaultdict(list))
    error_count: int = 0
    error_contexts: Counter = field(default_factory=Counter)
    sessions: list = field(default_factory=list)
    first_event: float = 0
    last_event: float = 0


def is_printable_key(key: str) -> bool:
    """Check if key produces a printable character."""
    return (
        key.startswith("KEY_") and
        len(key) == 5 and key[4].isalpha() or  # KEY_A through KEY_Z
        key in ("KEY_SPACE", "KEY_TAB") or
        key.startswith("KEY_") and key[4:].isdigit()  # KEY_0 through KEY_9
    )


def load_events(path: Path, start_date: datetime | None = None, end_date: datetime | None = None) -> list[dict]:
    """Load and filter events from JSONL file."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                ts = event["timestamp"]
                if start_date and ts < start_date.timestamp():
                    continue
                if end_date and ts > end_date.timestamp():
                    continue
                events.append(event)
            except (json.JSONDecodeError, KeyError):
                continue
    return sorted(events, key=lambda e: e["timestamp"])


def analyze(events: list[dict], session_gap: float = 60.0) -> AnalysisResult:
    """Analyze keystroke events."""
    result = AnalysisResult()

    if not events:
        return result

    result.first_event = events[0]["timestamp"]
    result.last_event = events[-1]["timestamp"]

    # Track state
    prev_key = None
    prev_time = None
    session_start = None
    session_keystrokes = 0
    session_chars = 0

    for event in events:
        result.total_keystrokes += 1

        if event["event"] != "press":
            continue

        result.total_press_events += 1
        key = event["key"]
        ts = event["timestamp"]

        result.key_frequency[key] += 1

        # Track sessions
        if session_start is None:
            session_start = ts

        if prev_time and (ts - prev_time) > session_gap:
            # End previous session
            result.sessions.append(TypingSession(
                start=session_start,
                end=prev_time,
                keystrokes=session_keystrokes,
                chars=session_chars
            ))
            session_start = ts
            session_keystrokes = 0
            session_chars = 0
            prev_key = None
            prev_time = None

        session_keystrokes += 1
        if is_printable_key(key):
            session_chars += 1

        # Track errors (backspace usage)
        if key == "KEY_BACKSPACE":
            result.error_count += 1
            if prev_key:
                result.error_contexts[prev_key] += 1

        # Track digraph timing
        if prev_key and prev_time:
            delta = ts - prev_time
            if delta < 2.0:  # Ignore pauses > 2 seconds
                digraph = f"{prev_key}->{key}"
                result.digraph_times[digraph].append(delta * 1000)  # Convert to ms

        prev_key = key
        prev_time = ts

    # Close final session
    if session_start is not None and prev_time is not None:
        result.sessions.append(TypingSession(
            start=session_start,
            end=prev_time,
            keystrokes=session_keystrokes,
            chars=session_chars
        ))

    return result


def compute_stats(result: AnalysisResult) -> dict:
    """Compute summary statistics from analysis result."""
    stats = {
        "total_keystrokes": result.total_keystrokes,
        "total_press_events": result.total_press_events,
        "error_count": result.error_count,
        "error_rate": result.error_count / result.total_press_events if result.total_press_events else 0,
        "session_count": len(result.sessions),
    }

    # Time range
    if result.first_event and result.last_event:
        stats["first_event"] = datetime.fromtimestamp(result.first_event).isoformat()
        stats["last_event"] = datetime.fromtimestamp(result.last_event).isoformat()
        stats["duration_hours"] = (result.last_event - result.first_event) / 3600

    # Top keys
    stats["top_keys"] = result.key_frequency.most_common(20)

    # Slow digraphs (high median time)
    digraph_medians = {}
    for digraph, times in result.digraph_times.items():
        if len(times) >= 5:  # Need at least 5 samples
            digraph_medians[digraph] = statistics.median(times)

    stats["slow_digraphs"] = sorted(
        digraph_medians.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    # Fast digraphs
    stats["fast_digraphs"] = sorted(
        digraph_medians.items(),
        key=lambda x: x[1]
    )[:20]

    # Error contexts (what keys precede backspace)
    stats["error_contexts"] = result.error_contexts.most_common(10)

    # WPM calculation (chars / 5 = words, per minute)
    total_chars = sum(s.chars for s in result.sessions)
    total_time_min = sum((s.end - s.start) / 60 for s in result.sessions)
    stats["total_chars"] = total_chars
    stats["total_typing_minutes"] = total_time_min
    if total_time_min > 0:
        stats["average_wpm"] = (total_chars / 5) / total_time_min
    else:
        stats["average_wpm"] = 0

    return stats


def main():
    parser = argparse.ArgumentParser(description="Analyze keystroke logs")
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path.home() / ".local/share/typing-analysis/keystrokes.jsonl",
        help="Input JSONL file"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output JSON file (default: print to stdout)"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--session-gap",
        type=float,
        default=60.0,
        help="Seconds of inactivity to end a session (default: 60)"
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    start_date = datetime.fromisoformat(args.start) if args.start else None
    end_date = datetime.fromisoformat(args.end) if args.end else None

    events = load_events(args.input, start_date, end_date)
    result = analyze(events, args.session_gap)
    stats = compute_stats(result)

    output = json.dumps(stats, indent=2, default=str)

    if args.output:
        args.output.write_text(output)
        print(f"Analysis written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
