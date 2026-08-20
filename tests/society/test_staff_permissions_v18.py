from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _permissions_source() -> str:
    return (ROOT / "app" / "society" / "permissions.py").read_text(encoding="utf-8")


def test_staff_overwrite_contains_approved_category_permissions():
    source = _permissions_source()
    start = source.index("def staff_overwrite()")
    end = source.index("\n\ndef base_category_overwrites", start)
    block = source[start:end]

    allowed = {
        "view_channel",
        "create_instant_invite",
        "send_messages",
        "send_messages_in_threads",
        "create_public_threads",
        "create_private_threads",
        "embed_links",
        "attach_files",
        "add_reactions",
        "use_external_emojis",
        "use_external_stickers",
        "mention_everyone",
        "manage_messages",
        "pin_messages",
        "bypass_slowmode",
        "manage_threads",
        "read_message_history",
        "send_polls",
        "connect",
        "speak",
        "stream",
        "use_soundboard",
        "use_external_sounds",
        "use_voice_activation",
        "priority_speaker",
        "mute_members",
        "deafen_members",
        "move_members",
        "set_voice_channel_status",
    }
    for permission in allowed:
        assert f"{permission}=True" in block, permission

    neutral = {
        "administrator",
        "manage_channels",
        "manage_roles",
        "manage_webhooks",
        "send_tts_messages",
        "send_voice_messages",
        "use_application_commands",
        "use_embedded_activities",
        "use_external_apps",
        "request_to_speak",
        "create_events",
        "manage_events",
    }
    for permission in neutral:
        assert f"{permission}=True" not in block, permission
        assert f"{permission}=False" not in block, permission


def test_existing_societies_are_reconciled_on_ready_once():
    source = (ROOT / "app" / "bot" / "client.py").read_text(encoding="utf-8")
    assert "self._staff_permissions_reconciled = False" in source
    assert "refresh_staff_category_permissions" in source
    assert "self._staff_permissions_reconciled = True" in source


def test_template_sync_reapplies_staff_permissions():
    source = (ROOT / "app" / "society" / "spaces.py").read_text(encoding="utf-8")
    start = source.index("async def sync_template(")
    block = source[start:]
    assert "await category.set_permissions(" in block
    assert "overwrite=staff_overwrite()" in block
    assert 'definition.channel_type in {"STAFF-TXT", "STAFF-VOICE"}' in block


def test_discord_py_27_is_required_for_new_permission_flags():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "discord.py>=2.7,<3" in requirements
