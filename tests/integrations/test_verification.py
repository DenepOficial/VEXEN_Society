from app.config.settings import Settings


def test_verification_can_be_disabled():
    settings = Settings(
        _env_file=None,
        verification_integration="disabled",
        society_db_schema=(
            "vexen_society_dev"
        ),
        vexmod_roles_schema=(
            "vexmod_temp_roles"
        ),
    )

    assert (
        settings.verification_integration
        == "disabled"
    )
