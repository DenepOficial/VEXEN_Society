from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_requires_discord_py_26():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "discord.py>=2.6,<3" in requirements


def test_onboarding_uses_public_discord_py_api_and_int_role():
    source = (
        ROOT / "app" / "integrations" / "onboarding.py"
    ).read_text(encoding="utf-8")
    assert "await guild.onboarding()" in source
    assert "await guild.edit_onboarding(" in source
    assert "discord.OnboardingPromptOption(" in source
    assert '"roles": [integration_role_id]' in source


def test_onboarding_option_uses_associate_display_name():
    source = (
        ROOT / "app" / "integrations" / "onboarding.py"
    ).read_text(encoding="utf-8")
    assert "identity = self._identity(display_name)" in source
    assert "title = identity.text" in source
    assert 'option_kwargs["emoji"] = identity.custom_emoji' in source
    assert "community_name" in source


def test_onboarding_is_removed_before_society_roles():
    source = (
        ROOT / "app" / "society" / "spaces.py"
    ).read_text(encoding="utf-8")
    remove_at = source.index("remove_associate_option(")
    role_delete_at = source.index("role_specs = [", remove_at)
    assert remove_at < role_delete_at


def test_onboarding_config_command_exists():
    source = (
        ROOT / "app" / "society" / "associates.py"
    ).read_text(encoding="utf-8")
    assert 'name="incorporacion"' in source
    assert '@configure_onboarding_prompt.autocomplete("pregunta")' in source
