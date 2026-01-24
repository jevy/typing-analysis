"""Tests for analyze.py"""

import json
import tempfile
from pathlib import Path

import pytest

from analyze import analyze, compute_stats, is_printable_key, load_events


def make_event(timestamp: float, key: str, event: str = "press") -> dict:
    """Create a test event."""
    return {
        "timestamp": timestamp,
        "datetime": "2025-01-01T00:00:00",
        "code": 0,
        "key": key,
        "event": event,
    }


class TestIsPrintableKey:
    def test_letter_keys(self):
        assert is_printable_key("KEY_A")
        assert is_printable_key("KEY_Z")

    def test_space(self):
        assert is_printable_key("KEY_SPACE")

    def test_tab(self):
        assert is_printable_key("KEY_TAB")

    def test_modifiers_not_printable(self):
        assert not is_printable_key("KEY_LEFTSHIFT")
        assert not is_printable_key("KEY_LEFTCTRL")
        assert not is_printable_key("KEY_BACKSPACE")


class TestAnalyze:
    def test_empty_events(self):
        result = analyze([])
        assert result.total_keystrokes == 0
        assert result.total_press_events == 0

    def test_counts_keystrokes(self):
        events = [
            make_event(1.0, "KEY_A", "press"),
            make_event(1.1, "KEY_A", "release"),
            make_event(1.2, "KEY_B", "press"),
            make_event(1.3, "KEY_B", "release"),
        ]
        result = analyze(events)
        assert result.total_keystrokes == 4
        assert result.total_press_events == 2

    def test_key_frequency(self):
        events = [
            make_event(1.0, "KEY_A"),
            make_event(1.1, "KEY_A"),
            make_event(1.2, "KEY_B"),
        ]
        result = analyze(events)
        assert result.key_frequency["KEY_A"] == 2
        assert result.key_frequency["KEY_B"] == 1

    def test_error_counting(self):
        events = [
            make_event(1.0, "KEY_A"),
            make_event(1.1, "KEY_BACKSPACE"),
            make_event(1.2, "KEY_B"),
            make_event(1.3, "KEY_BACKSPACE"),
        ]
        result = analyze(events)
        assert result.error_count == 2

    def test_error_context(self):
        events = [
            make_event(1.0, "KEY_A"),
            make_event(1.1, "KEY_BACKSPACE"),
            make_event(1.2, "KEY_A"),
            make_event(1.3, "KEY_BACKSPACE"),
        ]
        result = analyze(events)
        assert result.error_contexts["KEY_A"] == 2

    def test_digraph_timing(self):
        events = [
            make_event(1.0, "KEY_A"),
            make_event(1.1, "KEY_B"),  # 100ms after A
        ]
        result = analyze(events)
        assert "KEY_A->KEY_B" in result.digraph_times
        assert len(result.digraph_times["KEY_A->KEY_B"]) == 1
        assert abs(result.digraph_times["KEY_A->KEY_B"][0] - 100) < 1

    def test_session_detection(self):
        events = [
            make_event(1.0, "KEY_A"),
            make_event(1.1, "KEY_B"),
            # Gap > 60 seconds
            make_event(100.0, "KEY_C"),
            make_event(100.1, "KEY_D"),
        ]
        result = analyze(events, session_gap=60.0)
        assert len(result.sessions) == 2


class TestComputeStats:
    def test_wpm_calculation(self):
        events = [make_event(i * 0.2, "KEY_A") for i in range(50)]  # 50 chars in 10 seconds
        result = analyze(events)
        stats = compute_stats(result)
        # 50 chars / 5 = 10 words in 10 seconds = 60 WPM
        assert stats["average_wpm"] > 50  # Approximate

    def test_error_rate(self):
        events = [
            make_event(1.0, "KEY_A"),
            make_event(1.1, "KEY_B"),
            make_event(1.2, "KEY_BACKSPACE"),
            make_event(1.3, "KEY_C"),
        ]
        result = analyze(events)
        stats = compute_stats(result)
        assert stats["error_rate"] == 0.25  # 1 backspace / 4 presses


class TestLoadEvents:
    def test_loads_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(make_event(1.0, "KEY_A")) + "\n")
            f.write(json.dumps(make_event(2.0, "KEY_B")) + "\n")
            path = Path(f.name)

        try:
            events = load_events(path)
            assert len(events) == 2
            assert events[0]["key"] == "KEY_A"
            assert events[1]["key"] == "KEY_B"
        finally:
            path.unlink()

    def test_handles_empty_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(make_event(1.0, "KEY_A")) + "\n")
            f.write("\n")
            f.write(json.dumps(make_event(2.0, "KEY_B")) + "\n")
            path = Path(f.name)

        try:
            events = load_events(path)
            assert len(events) == 2
        finally:
            path.unlink()
