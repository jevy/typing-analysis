"""Tests for report.py"""

import pytest

from report import format_duration, format_key, format_digraph


class TestFormatDuration:
    def test_seconds(self):
        assert format_duration(30) == "30.0s"

    def test_minutes(self):
        assert format_duration(120) == "2.0m"

    def test_hours(self):
        assert format_duration(7200) == "2.0h"


class TestFormatKey:
    def test_strips_key_prefix(self):
        assert format_key("KEY_A") == "A"
        assert format_key("KEY_BACKSPACE") == "BACKSPACE"

    def test_no_prefix(self):
        assert format_key("SPACE") == "SPACE"


class TestFormatDigraph:
    def test_formats_digraph(self):
        assert format_digraph("KEY_A->KEY_B") == "A -> B"

    def test_handles_invalid(self):
        assert format_digraph("invalid") == "invalid"
