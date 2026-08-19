from pathlib import Path


def test_delete_stops_before_role_cleanup_if_onboarding_fails():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "society"
        / "spaces.py"
    ).read_text(encoding="utf-8")

    assert "if onboarding_delete_failed:" in source
    assert "SOCIETY_DELETE_BLOCKED_ONBOARDING" in source
    assert "return report" in source[
        source.index("if onboarding_delete_failed:"):
        source.index("if integration_role_id:", source.index("if onboarding_delete_failed:"))
    ]
