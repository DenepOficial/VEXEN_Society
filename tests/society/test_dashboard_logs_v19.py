from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_log_service_exposes_expected_commands_and_safe_dispatcher():
    source = (ROOT / "app" / "society" / "logs.py").read_text(encoding="utf-8")
    assert 'name="canal_logs"' in source
    assert 'name="probar_logs"' in source
    assert "log_channel_id" in source
    assert "discord_log_state" in source
    assert "except discord.Forbidden" in source
    assert "except discord.HTTPException" in source


def test_dashboard_worker_accepts_log_channel_and_audits_admin_actions():
    source = (ROOT / "app" / "bot" / "control_jobs.py").read_text(encoding="utf-8")
    assert '"log_channel_id": "bigint"' in source
    assert "DASHBOARD_CONFIG_UPDATED" in source
    assert "DASHBOARD_STAFF_ADDED" in source
    assert "DASHBOARD_ALLOWED_ROLE_ADDED" in source
