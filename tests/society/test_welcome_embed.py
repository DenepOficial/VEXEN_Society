from pathlib import Path


def test_welcome_heading_is_outside_embed():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "society"
        / "welcome.py"
    ).read_text(encoding="utf-8")

    assert 'content="# 🎉 ¡BIENVENIDOS A VEXEN SOCIETY!"' in source
    assert 'title="🎉 ¡BIENVENIDOS A VEXEN SOCIETY!"' not in source
