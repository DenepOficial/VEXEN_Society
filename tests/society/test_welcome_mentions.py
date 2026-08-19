from pathlib import Path

def source():
    return (Path(__file__).resolve().parents[2] / "app" / "society" / "welcome.py").read_text(encoding="utf-8")

def test_welcome_uses_real_user_mention():
    text = source()
    assert 'associate_mention = f"<@{associate_user_id}>"' in text
    assert "users=True" in text

def test_join_button_uses_community_name_and_no_old_text():
    text = source()
    assert "label=build_community_join_label(community_name)" in text
    assert 'label="Unirme a esta comunidad"' not in text
