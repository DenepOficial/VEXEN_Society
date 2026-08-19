import pytest
from app.society.button_config import (
    DEFAULT_ANNOUNCEMENT_BUTTON_STYLE,
    DEFAULT_WELCOME_BUTTON_STYLE,
    build_community_join_label,
    community_button_style_label,
    normalize_community_button_style,
)


def test_independent_default_button_styles():
    assert DEFAULT_WELCOME_BUTTON_STYLE == "success"
    assert DEFAULT_ANNOUNCEMENT_BUTTON_STYLE == "secondary"


def test_normalize_button_styles():
    assert normalize_community_button_style("PRIMARY") == "primary"
    assert normalize_community_button_style(" secondary ") == "secondary"
    assert normalize_community_button_style("success") == "success"
    assert normalize_community_button_style("danger") == "danger"


def test_rejects_black_custom_style():
    with pytest.raises(ValueError):
        normalize_community_button_style("black")


def test_style_label_describes_color():
    assert community_button_style_label("secondary") == "secondary — Gris / oscuro"


def test_dynamic_join_label():
    assert build_community_join_label("LosPoPiWa") == "Unirme a LosPoPiWa"


def test_dynamic_join_label_max_80():
    assert len(build_community_join_label("X" * 100)) <= 80
