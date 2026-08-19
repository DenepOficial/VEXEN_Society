from pathlib import Path

from app.society.identity import parse_society_display_identity


def test_identity_splits_custom_emoji_from_visible_title():
    identity = parse_society_display_identity(
        "<:logo:1538690277991120938> Prueba"
    )

    assert identity.raw == "<:logo:1538690277991120938> Prueba"
    assert identity.text == "Prueba"
    assert identity.custom_emoji == "<:logo:1538690277991120938>"


def test_identity_supports_animated_custom_emoji():
    identity = parse_society_display_identity(
        "<a:logo:1538690277991120938> Prueba"
    )

    assert identity.text == "Prueba"
    assert identity.custom_emoji == "<a:logo:1538690277991120938>"


def test_onboarding_uses_clean_title_and_separate_emoji_field():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "integrations"
        / "onboarding.py"
    ).read_text(encoding="utf-8")

    assert "parse_society_display_identity" in source
    assert 'option_kwargs["emoji"] = identity.custom_emoji' in source
    assert "title = identity.text" in source


def test_onboarding_delete_verifies_the_int_role_is_gone():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "integrations"
        / "onboarding.py"
    ).read_text(encoding="utf-8")

    assert (
        "Discord no confirmó la eliminación de la opción de incorporación."
        in source
    )
