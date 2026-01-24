#!/usr/bin/env python3
"""Generate human-readable typing analysis reports."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from analyze import analyze, compute_stats, load_events, compute_rolling_stats


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


def print_report(stats: dict, rolling_stats: dict | None = None):
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

    # Rolling averages comparison
    if rolling_stats:
        print("PROGRESS OVER TIME")
        print("-" * 40)
        print(f"{'':20} {'Today':>12} {'7-Day Avg':>12} {'30-Day Avg':>12}")

        today_wpm = stats['average_wpm']
        week_wpm = rolling_stats.get('week', {}).get('average_wpm', 0)
        month_wpm = rolling_stats.get('month', {}).get('average_wpm', 0)
        print(f"{'WPM:':20} {today_wpm:>12.1f} {week_wpm:>12.1f} {month_wpm:>12.1f}")

        today_err = stats['error_rate'] * 100
        week_err = rolling_stats.get('week', {}).get('error_rate', 0) * 100
        month_err = rolling_stats.get('month', {}).get('error_rate', 0) * 100
        print(f"{'Error Rate:':20} {today_err:>11.1f}% {week_err:>11.1f}% {month_err:>11.1f}%")
        print()

    # Long key holds (homerow mod debugging)
    if stats.get("long_holds"):
        print("LONG KEY HOLDS (potential homerow mod issues)")
        print("-" * 40)
        # Group by key and show counts
        hold_counts = {}
        for hold in stats["long_holds"]:
            key = hold["key"]
            hold_counts[key] = hold_counts.get(key, 0) + 1
        for key, count in sorted(hold_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {format_key(key):20} {count:,} long holds (>=200ms)")
        print()

    # Hold duration stats
    if stats.get("hold_duration_stats"):
        print("KEY HOLD DURATIONS (avg/max)")
        print("-" * 40)
        for key, hold_info in stats["hold_duration_stats"][:10]:
            avg = hold_info["avg"]
            max_hold = hold_info["max"]
            flag = " <-- check this" if max_hold >= 200 else ""
            print(f"  {format_key(key):15} avg:{avg:>4.0f}ms  max:{max_hold:>4.0f}ms{flag}")
        print()

    # Idle time distribution
    if stats.get("idle_time_distribution"):
        dist = stats["idle_time_distribution"]
        print("TYPING RHYTHM (idle time between keys)")
        print("-" * 40)
        total = (dist["short_under_100ms"] + dist["medium_100_500ms"] +
                 dist["long_500_2000ms"] + dist["very_long_over_2000ms"])
        if total > 0:
            print(f"  Fast flow (<100ms):     {dist['short_under_100ms']:>6,} ({dist['short_under_100ms']/total*100:>5.1f}%)")
            print(f"  Normal (100-500ms):     {dist['medium_100_500ms']:>6,} ({dist['medium_100_500ms']/total*100:>5.1f}%)")
            print(f"  Pauses (500ms-2s):      {dist['long_500_2000ms']:>6,} ({dist['long_500_2000ms']/total*100:>5.1f}%)")
            print(f"  Long pauses (>2s):      {dist['very_long_over_2000ms']:>6,} ({dist['very_long_over_2000ms']/total*100:>5.1f}%)")
            print(f"  Median idle: {dist['median_idle_ms']:.0f}ms")
        print()

    # Time of day analysis
    if stats.get("time_of_day"):
        print("TIME OF DAY ANALYSIS")
        print("-" * 40)
        period_order = ["morning", "afternoon", "evening", "night"]
        period_labels = {
            "morning": "Morning (6am-12pm)",
            "afternoon": "Afternoon (12pm-6pm)",
            "evening": "Evening (6pm-12am)",
            "night": "Night (12am-6am)",
        }
        for period in period_order:
            if period in stats["time_of_day"]:
                data = stats["time_of_day"][period]
                err_pct = data["error_rate"] * 100
                flag = " <-- consider breaks" if err_pct > 10 else ""
                print(f"  {period_labels[period]:25} {data['presses']:>6,} keys, {err_pct:>5.1f}% errors{flag}")
        print()

    # Fatigue detection
    if stats.get("fatigue_analysis"):
        print("FATIGUE DETECTION")
        print("-" * 40)
        for i, session in enumerate(stats["fatigue_analysis"][:5], 1):
            status = "Warning: Fatigue detected" if session["fatigue_detected"] else "Stable"
            change = session["change_percent"]
            change_str = f"+{change:.0f}%" if change > 0 else f"{change:.0f}%"
            print(f"  Session {i} ({session['duration_minutes']:.0f}min): "
                  f"{session['start_error_rate']*100:.1f}% -> {session['end_error_rate']*100:.1f}% "
                  f"({change_str}) {status}")
        print()

    # Typo patterns
    if stats.get("typo_patterns"):
        print("COMMON TYPOS")
        print("-" * 40)
        for typo in stats["typo_patterns"][:10]:
            print(f"  {typo['original']:10} -> {typo['corrected']:10} ({typo['count']} times)")
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

    # Load all events for rolling stats comparison
    all_events = load_events(args.input)
    rolling_stats = None
    if len(all_events) > len(events):  # Only if we have more historical data
        rolling_stats = {
            "week": compute_rolling_stats(all_events, 7),
            "month": compute_rolling_stats(all_events, 30),
        }

    if args.json:
        import json
        output = {"current": stats}
        if rolling_stats:
            output["rolling"] = rolling_stats
        print(json.dumps(output, indent=2, default=str))
    else:
        print_report(stats, rolling_stats)


if __name__ == "__main__":
    main()
