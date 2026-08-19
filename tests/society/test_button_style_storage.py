from pathlib import Path


def test_database_has_independent_style_columns_and_accessors():
    text = (Path(__file__).resolve().parents[2]/"database.py").read_text(encoding="utf-8")
    assert "welcome_button_style TEXT NOT NULL DEFAULT 'success'" in text
    assert "announcement_button_style TEXT NOT NULL DEFAULT 'secondary'" in text
    assert "async def get_welcome_button_style(" in text
    assert "async def set_welcome_button_style(" in text
    assert "async def get_announcement_button_style(" in text
    assert "async def set_announcement_button_style(" in text


def test_flows_read_different_settings():
    root = Path(__file__).resolve().parents[2]
    welcome = (root/"app"/"society"/"welcome.py").read_text(encoding="utf-8")
    announcements = (root/"app"/"society"/"announcements.py").read_text(encoding="utf-8")
    assert "get_welcome_button_style" in welcome
    assert "get_announcement_button_style" in announcements
