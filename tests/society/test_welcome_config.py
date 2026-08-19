import pytest

from app.society.welcome_config import (
    DEFAULT_WELCOME_COLOR_HEX,
    normalize_welcome_color,
    welcome_color_to_int,
)


def test_default_welcome_color():
    assert normalize_welcome_color("default") == DEFAULT_WELCOME_COLOR_HEX


def test_accepts_hex_with_or_without_hash():
    assert normalize_welcome_color("#57f287") == "#57F287"
    assert normalize_welcome_color("ff5b00") == "#FF5B00"


def test_rejects_invalid_hex():
    with pytest.raises(ValueError):
        normalize_welcome_color("#ZZZZZZ")


def test_hex_to_int():
    assert welcome_color_to_int("#57F287") == 0x57F287
