from pathlib import Path


def _config_status_block() -> str:
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "society"
        / "associates.py"
    ).read_text(encoding="utf-8")

    start = source.index("    async def config_status(")
    return source[start:]


def test_config_status_defers_before_slow_checks():
    block = _config_status_block()

    defer_pos = block.index("await interaction.response.defer(")
    onboarding_pos = block.index(
        "await self.bot.onboarding_integration.status(interaction.guild)"
    )

    assert defer_pos < onboarding_pos
    assert "ephemeral=True" in block[defer_pos:onboarding_pos]
    assert "thinking=True" in block[defer_pos:onboarding_pos]


def test_config_status_responds_with_followup_after_defer():
    block = _config_status_block()
    assert "await interaction.followup.send(" in block
