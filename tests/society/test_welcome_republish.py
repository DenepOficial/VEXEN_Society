from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_welcome_republish_command_exists_and_is_by_associate():
    source = (ROOT / "app" / "society" / "associates.py").read_text(encoding="utf-8")
    assert 'name="bienvenida"' in source
    assert 'name="reenviar"' in source
    assert "asociado: discord.Member" in source
    assert "await publish_welcome(" in source


def test_old_button_is_disabled_only_after_new_welcome_is_published():
    source = (ROOT / "app" / "society" / "associates.py").read_text(encoding="utf-8")
    start = source.index("async def resend_welcome(")
    block = source[start:source.index("    @asociado.command(", start)]
    publish_at = block.index("await publish_welcome(")
    success_guard_at = block.index("if message is None:")
    disable_at = block.index("await disable_welcome_button(")
    assert publish_at < success_guard_at < disable_at
    assert '"WELCOME_REPUBLISHED"' in block
