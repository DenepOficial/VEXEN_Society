from pathlib import Path


def test_restore_query_includes_source_message_id():
    database_py = (
        Path(__file__).resolve().parents[2] / "database.py"
    ).read_text(encoding="utf-8")

    start = database_py.index(
        "async def list_active_announcement_role_button_bindings"
    )
    end = database_py.index(
        "async def delete_announcement_mirror",
        start,
    )
    block = database_py[start:end]

    assert "m.source_message_id" in block
