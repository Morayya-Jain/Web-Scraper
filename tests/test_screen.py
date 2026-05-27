"""Tests for screen._parse_claude_reply - the JSON-extraction logic."""
from __future__ import annotations

from screen import _parse_claude_reply


def test_clean_json():
    out = _parse_claude_reply(
        '{"role_fit": 9, "level_fit": 8, "visa_fit": "yes", "reason": "tech grad"}'
    )
    assert out == {
        "role_fit": 9,
        "level_fit": 8,
        "visa_fit": "yes",
        "reason": "tech grad",
    }


def test_fenced_json():
    out = _parse_claude_reply(
        '```json\n{"role_fit": 7, "level_fit": 6, "visa_fit": "unclear", "reason": "ok"}\n```'
    )
    assert out["role_fit"] == 7
    assert out["level_fit"] == 6
    assert out["visa_fit"] == "unclear"


def test_out_of_range_fit_clipped():
    out = _parse_claude_reply(
        '{"role_fit": 15, "level_fit": -3, "visa_fit": "yes", "reason": "x"}'
    )
    assert out["role_fit"] == 10
    assert out["level_fit"] == 0


def test_unknown_visa_value_becomes_unclear():
    out = _parse_claude_reply(
        '{"role_fit": 5, "level_fit": 5, "visa_fit": "maybe", "reason": "x"}'
    )
    assert out["visa_fit"] == "unclear"


def test_malformed_json_defaults_to_failure():
    out = _parse_claude_reply("not actually json at all")
    assert out["role_fit"] == 0
    assert out["visa_fit"] == "unclear"
    assert "screen failed" in out["reason"]


def test_missing_fields_default_to_zero():
    out = _parse_claude_reply('{"reason": "no scores"}')
    assert out["role_fit"] == 0
    assert out["level_fit"] == 0
    assert out["visa_fit"] == "unclear"


def test_non_object_json_defaults_to_failure():
    out = _parse_claude_reply('["wrong", "shape"]')
    assert out["role_fit"] == 0
    assert "screen failed" in out["reason"]
