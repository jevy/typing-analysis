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
    # New fields for enhanced analysis
    hold_durations: dict = field(default_factory=lambda: defaultdict(list))  # key -> [durations]
    long_holds: list = field(default_factory=list)  # [(key, duration_ms, timestamp)]
    idle_times: list = field(default_factory=list)  # [idle_ms values]
    hourly_stats: dict = field(default_factory=lambda: defaultdict(lambda: {"presses": 0, "errors": 0, "chars": 0}))
    typo_sequences: list = field(default_factory=list)  # [(before, after, count)]
    raw_events: list = field(default_factory=list)  # For typo detection


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


def analyze(events: list[dict], session_gap: float = 60.0, long_hold_threshold_ms: int = 200) -> AnalysisResult:
    """Analyze keystroke events."""
    result = AnalysisResult()

    if not events:
        return result

    result.first_event = events[0]["timestamp"]
    result.last_event = events[-1]["timestamp"]
    result.raw_events = events  # Store for typo detection

    # Track state
    prev_key = None
    prev_time = None
    session_start = None
    session_keystrokes = 0
    session_chars = 0

    for event in events:
        result.total_keystrokes += 1
        ts = event["timestamp"]
        key = event["key"]

        # Track hold durations from release events
        if event["event"] == "release" and "hold_duration_ms" in event:
            hold_ms = event["hold_duration_ms"]
            result.hold_durations[key].append(hold_ms)
            if hold_ms >= long_hold_threshold_ms:
                result.long_holds.append((key, hold_ms, ts))

        if event["event"] != "press":
            continue

        result.total_press_events += 1

        result.key_frequency[key] += 1

        # Track idle times
        if "idle_before_ms" in event:
            result.idle_times.append(event["idle_before_ms"])

        # Track hourly stats
        hour = datetime.fromtimestamp(ts).hour
        result.hourly_stats[hour]["presses"] += 1
        if is_printable_key(key):
            result.hourly_stats[hour]["chars"] += 1
        if key == "KEY_BACKSPACE":
            result.hourly_stats[hour]["errors"] += 1

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

    # Detect typo patterns
    result.typo_sequences = detect_typo_patterns(events)

    return result


def key_to_char(key: str, shift_active: bool = False) -> str | None:
    """Convert KEY_* code to character. Returns None for non-printable keys."""
    if key.startswith("KEY_") and len(key) == 5 and key[4].isalpha():
        char = key[4].lower()
        return char.upper() if shift_active else char
    if key == "KEY_SPACE":
        return " "
    if key.startswith("KEY_") and len(key) == 5 and key[4].isdigit():
        return key[4]
    return None


def detect_typo_patterns(events: list[dict]) -> list[tuple[str, str, int]]:
    """Detect typo patterns: sequences typed, deleted, then retyped differently.

    Returns list of (original, corrected, count) tuples.
    """
    typo_counts: Counter = Counter()

    # Build sequence of characters with backspace markers
    press_events = [e for e in events if e["event"] == "press"]

    i = 0
    while i < len(press_events):
        # Look for backspace sequences
        if press_events[i]["key"] == "KEY_BACKSPACE":
            # Count consecutive backspaces
            backspace_count = 0
            j = i
            while j < len(press_events) and press_events[j]["key"] == "KEY_BACKSPACE":
                backspace_count += 1
                j += 1

            # Get characters before backspaces (what was deleted)
            deleted_chars = []
            shift_active = False
            for k in range(max(0, i - backspace_count - 5), i):
                key = press_events[k]["key"]
                if key in ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"):
                    shift_active = True
                    continue
                char = key_to_char(key, shift_active)
                if char:
                    deleted_chars.append(char)
                shift_active = False

            deleted = "".join(deleted_chars[-backspace_count:]) if deleted_chars else ""

            # Get characters after backspaces (replacement)
            replacement_chars = []
            shift_active = False
            for k in range(j, min(j + len(deleted) + 2, len(press_events))):
                key = press_events[k]["key"]
                if key == "KEY_BACKSPACE":
                    break
                if key in ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"):
                    shift_active = True
                    continue
                char = key_to_char(key, shift_active)
                if char:
                    replacement_chars.append(char)
                shift_active = False

            replacement = "".join(replacement_chars[:len(deleted) + 1])

            # Record if we found a meaningful pattern
            if len(deleted) >= 2 and len(replacement) >= 2 and deleted != replacement:
                typo_counts[(deleted, replacement)] += 1

            i = j
        else:
            i += 1

    # Return top patterns
    return [(orig, repl, count) for (orig, repl), count in typo_counts.most_common(20)]


def compute_time_of_day_stats(result: AnalysisResult) -> dict:
    """Compute typing stats by time of day periods."""
    periods = {
        "morning": range(6, 12),
        "afternoon": range(12, 18),
        "evening": range(18, 24),
        "night": list(range(0, 6)),
    }

    period_stats = {}
    for period_name, hours in periods.items():
        presses = sum(result.hourly_stats[h]["presses"] for h in hours)
        errors = sum(result.hourly_stats[h]["errors"] for h in hours)
        chars = sum(result.hourly_stats[h]["chars"] for h in hours)

        if presses > 0:
            period_stats[period_name] = {
                "presses": presses,
                "errors": errors,
                "chars": chars,
                "error_rate": errors / presses if presses else 0,
            }

    return period_stats


def compute_fatigue_analysis(result: AnalysisResult, window_minutes: int = 10) -> list[dict]:
    """Analyze error rate trends within sessions to detect fatigue.

    Returns list of session analyses with fatigue indicators.
    """
    fatigue_data = []

    for session in result.sessions:
        session_duration = session.end - session.start
        if session_duration < window_minutes * 60:  # Skip short sessions
            continue

        # Get events in this session
        session_events = [
            e for e in result.raw_events
            if session.start <= e["timestamp"] <= session.end and e["event"] == "press"
        ]

        if len(session_events) < 20:  # Need enough data
            continue

        # Split into windows
        windows = []
        window_start = session.start
        while window_start < session.end:
            window_end = window_start + (window_minutes * 60)
            window_events = [
                e for e in session_events
                if window_start <= e["timestamp"] < window_end
            ]
            if window_events:
                errors = sum(1 for e in window_events if e["key"] == "KEY_BACKSPACE")
                error_rate = errors / len(window_events) if window_events else 0
                windows.append({"error_rate": error_rate, "events": len(window_events)})
            window_start = window_end

        if len(windows) >= 2:
            first_rate = windows[0]["error_rate"]
            last_rate = windows[-1]["error_rate"]
            change_pct = ((last_rate - first_rate) / first_rate * 100) if first_rate > 0 else 0

            fatigue_data.append({
                "duration_minutes": session_duration / 60,
                "windows": len(windows),
                "start_error_rate": first_rate,
                "end_error_rate": last_rate,
                "change_percent": change_pct,
                "fatigue_detected": change_pct > 50,
            })

    return fatigue_data


def compute_rolling_stats(events: list[dict], days: int) -> dict | None:
    """Compute stats for the past N days."""
    if not events:
        return None

    cutoff = datetime.now().timestamp() - (days * 24 * 3600)
    filtered = [e for e in events if e["timestamp"] >= cutoff]

    if not filtered:
        return None

    result = analyze(filtered)
    stats = compute_stats(result)
    return stats


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

    # --- NEW STATS ---

    # Hold duration stats
    if result.hold_durations:
        hold_stats = {}
        for key, durations in result.hold_durations.items():
            if len(durations) >= 3:
                hold_stats[key] = {
                    "avg": statistics.mean(durations),
                    "max": max(durations),
                    "count": len(durations),
                }
        # Sort by max hold duration to find problematic keys
        stats["hold_duration_stats"] = sorted(
            hold_stats.items(),
            key=lambda x: x[1]["max"],
            reverse=True
        )[:15]

    # Long holds (potential accidental modifier activations)
    stats["long_holds"] = [
        {"key": k, "duration_ms": d, "timestamp": datetime.fromtimestamp(ts).isoformat()}
        for k, d, ts in result.long_holds[-20:]  # Last 20
    ]

    # Idle time distribution
    if result.idle_times:
        short_idles = sum(1 for t in result.idle_times if t < 100)
        medium_idles = sum(1 for t in result.idle_times if 100 <= t < 500)
        long_idles = sum(1 for t in result.idle_times if 500 <= t < 2000)
        very_long_idles = sum(1 for t in result.idle_times if t >= 2000)

        stats["idle_time_distribution"] = {
            "short_under_100ms": short_idles,
            "medium_100_500ms": medium_idles,
            "long_500_2000ms": long_idles,
            "very_long_over_2000ms": very_long_idles,
            "avg_idle_ms": statistics.mean(result.idle_times) if result.idle_times else 0,
            "median_idle_ms": statistics.median(result.idle_times) if result.idle_times else 0,
        }

    # Time of day stats
    stats["time_of_day"] = compute_time_of_day_stats(result)

    # Fatigue analysis
    stats["fatigue_analysis"] = compute_fatigue_analysis(result)

    # Typo patterns
    stats["typo_patterns"] = [
        {"original": orig, "corrected": corr, "count": count}
        for orig, corr, count in result.typo_sequences[:10]
    ]

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
