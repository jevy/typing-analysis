#!/usr/bin/env python3
"""Generate human-readable typing analysis reports."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from analyze import analyze, compute_stats, load_events


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def format_key(key: str) -> str:
    """Format key name for display."""
    if key.startswith("KEY_"):
        return key[4:]
    return key


def format_digraph(digraph: str) -> str:
    """Format digraph for display."""
    parts = digraph.split("->")
    if len(parts) == 2:
        return f"{format_key(parts[0])} -> {format_key(parts[1])}"
    return digraph


def print_report(stats: dict):
    """Print formatted report to stdout."""
    print("=" * 60)
    print("TYPING ANALYSIS REPORT")
    print("=" * 60)
    print()

    # Time range
    if "first_event" in stats:
        print(f"Period: {stats['first_event'][:10]} to {stats['last_event'][:10]}")
        print(f"Total duration: {stats['duration_hours']:.1f} hours")
        print()

    # Overall stats
    print("OVERALL STATISTICS")
    print("-" * 40)
    print(f"Total keystrokes: {stats['total_press_events']:,}")
    print(f"Typing sessions: {stats['session_count']}")
    print(f"Total typing time: {stats['total_typing_minutes']:.1f} minutes")
    print(f"Average WPM: {stats['average_wpm']:.1f}")
    print(f"Errors (backspaces): {stats['error_count']:,}")
    print(f"Error rate: {stats['error_rate']*100:.1f}%")
    print()

    # Slow digraphs (areas for improvement)
    if stats.get("slow_digraphs"):
        print("SLOWEST KEY TRANSITIONS (practice these)")
        print("-" * 40)
        for digraph, ms in stats["slow_digraphs"][:10]:
            print(f"  {format_digraph(digraph):25} {ms:.0f}ms")
        print()

    # Error contexts
    if stats.get("error_contexts"):
        print("KEYS BEFORE BACKSPACE (error-prone keys)")
        print("-" * 40)
        for key, count in stats["error_contexts"][:10]:
            print(f"  {format_key(key):20} {count:,} errors")
        print()

    # Top keys
    if stats.get("top_keys"):
        print("MOST USED KEYS")
        print("-" * 40)
        for key, count in stats["top_keys"][:10]:
            print(f"  {format_key(key):20} {count:,}")
        print()

    # Fast digraphs (your strengths)
    if stats.get("fast_digraphs"):
        print("FASTEST KEY TRANSITIONS (your strengths)")
        print("-" * 40)
        for digraph, ms in stats["fast_digraphs"][:10]:
            print(f"  {format_digraph(digraph):25} {ms:.0f}ms")
        print()


def main():
    parser = argparse.ArgumentParser(description="Generate typing analysis report")
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path.home() / ".local/share/typing-analysis/keystrokes.jsonl",
        help="Input JSONL file"
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
        "--today",
        action="store_true",
        help="Only show today's data"
    )
    parser.add_argument(
        "--week",
        action="store_true",
        help="Only show past 7 days"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted report"
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        print("Run the logger first to capture keystroke data.", file=sys.stderr)
        sys.exit(1)

    # Handle date shortcuts
    start_date = None
    end_date = None

    if args.today:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif args.week:
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=7)
    elif args.start:
        start_date = datetime.fromisoformat(args.start)

    if args.end:
        end_date = datetime.fromisoformat(args.end)

    events = load_events(args.input, start_date, end_date)

    if not events:
        print("No keystroke data found for the specified period.", file=sys.stderr)
        sys.exit(1)

    result = analyze(events)
    stats = compute_stats(result)

    if args.json:
        import json
        print(json.dumps(stats, indent=2, default=str))
    else:
        print_report(stats)


if __name__ == "__main__":
    main()
