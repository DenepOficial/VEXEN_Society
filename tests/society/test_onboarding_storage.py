from pathlib import Path


def test_onboarding_prompt_config_has_id_and_title_migration():
    source = (
        Path(__file__).resolve().parents[2] / "database.py"
    ).read_text(encoding="utf-8")
    assert "onboarding_prompt_id BIGINT" in source
    assert "onboarding_prompt_title TEXT" in source
    assert "async def set_onboarding_prompt_config(" in source
    assert "async def get_onboarding_prompt_config(" in source
