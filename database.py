from __future__ import annotations

import json
import re
from typing import Any

import asyncpg

_SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


def _schema_name(value: str) -> str:
    value = value.strip()
    if not _SCHEMA_PATTERN.fullmatch(value):
        raise ValueError("Nombre de schema PostgreSQL inválido.")
    return value


async def create_pool(database_url: str, society_schema: str) -> asyncpg.Pool:
    if not database_url.strip():
        raise RuntimeError("DATABASE_URL no está configurado.")
    society_schema = _schema_name(society_schema)
    pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )
    await create_tables(pool, society_schema)
    return pool


async def create_tables(db: asyncpg.Pool, schema: str) -> None:
    schema = _schema_name(schema)
    await db.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".allowed_roles (
            guild_id BIGINT NOT NULL,
            role_id BIGINT NOT NULL,
            added_by BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (guild_id, role_id)
        )
    ''')

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".settings (
            guild_id BIGINT PRIMARY KEY,
            global_announcements_channel_id BIGINT,
            base_category_id BIGINT,
            welcome_channel_id BIGINT,
            welcome_color_hex TEXT NOT NULL DEFAULT '#57F287',
            community_button_style TEXT NOT NULL DEFAULT 'secondary',
            welcome_button_style TEXT NOT NULL DEFAULT 'success',
            announcement_button_style TEXT NOT NULL DEFAULT 'secondary',
            onboarding_prompt_id BIGINT,
            onboarding_prompt_title TEXT,
            updated_by BIGINT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    ''')

    # Migraciones idempotentes para instalaciones v1.0 existentes.
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        'ADD COLUMN IF NOT EXISTS base_category_id BIGINT'
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        'ADD COLUMN IF NOT EXISTS welcome_channel_id BIGINT'
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        "ADD COLUMN IF NOT EXISTS welcome_color_hex TEXT NOT NULL DEFAULT '#57F287'"
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        "ADD COLUMN IF NOT EXISTS community_button_style TEXT NOT NULL DEFAULT 'secondary'"
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        "ADD COLUMN IF NOT EXISTS welcome_button_style TEXT NOT NULL DEFAULT 'success'"
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        "ADD COLUMN IF NOT EXISTS announcement_button_style TEXT NOT NULL DEFAULT 'secondary'"
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        'ADD COLUMN IF NOT EXISTS onboarding_prompt_id BIGINT'
    )
    await db.execute(
        f'ALTER TABLE "{schema}".settings '
        'ADD COLUMN IF NOT EXISTS onboarding_prompt_title TEXT'
    )

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".associates (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            display_name TEXT NOT NULL,
            community_name TEXT NOT NULL,
            community_role_id BIGINT,
            added_by BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (guild_id, user_id),
            CHECK (length(btrim(display_name)) BETWEEN 1 AND 100),
            CHECK (length(btrim(community_name)) BETWEEN 1 AND 80)
        )
    ''')

    await db.execute(f'''
        CREATE UNIQUE INDEX IF NOT EXISTS associates_community_name_unique
        ON "{schema}".associates (guild_id, lower(community_name))
    ''')

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".associate_spaces (
            guild_id BIGINT NOT NULL,
            associate_user_id BIGINT NOT NULL,
            category_id BIGINT UNIQUE,
            community_role_id BIGINT,
            integration_role_id BIGINT,
            staff_role_id BIGINT,
            template_id BIGINT,
            template_version INTEGER,
            welcome_channel_id BIGINT,
            welcome_message_id BIGINT,
            status TEXT NOT NULL DEFAULT 'creating',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (guild_id, associate_user_id),
            FOREIGN KEY (guild_id, associate_user_id)
                REFERENCES "{schema}".associates(guild_id, user_id)
                ON DELETE CASCADE,
            CHECK (status IN ('creating', 'active', 'deleting', 'error'))
        )
    ''')

    await db.execute(
        f'ALTER TABLE "{schema}".associate_spaces '
        'ADD COLUMN IF NOT EXISTS welcome_channel_id BIGINT'
    )
    await db.execute(
        f'ALTER TABLE "{schema}".associate_spaces '
        'ADD COLUMN IF NOT EXISTS welcome_message_id BIGINT'
    )

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".associate_channels (
            guild_id BIGINT NOT NULL,
            associate_user_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            channel_key TEXT NOT NULL,
            channel_type TEXT NOT NULL,
            is_template BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (guild_id, channel_id),
            UNIQUE (guild_id, associate_user_id, channel_key),
            FOREIGN KEY (guild_id, associate_user_id)
                REFERENCES "{schema}".associate_spaces(guild_id, associate_user_id)
                ON DELETE CASCADE,
            CHECK (channel_type IN ('ANN','TXT','STAFF-TXT','VOICE','STAFF-VOICE'))
        )
    ''')

    await db.execute(f'''
        CREATE INDEX IF NOT EXISTS associate_channels_owner_idx
        ON "{schema}".associate_channels(guild_id, associate_user_id)
    ''')

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".category_templates (
            template_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            version INTEGER NOT NULL,
            raw_template TEXT NOT NULL,
            parsed_template JSONB NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            uploaded_by BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (guild_id, version),
            CHECK (length(btrim(name)) BETWEEN 1 AND 100),
            CHECK (version > 0)
        )
    ''')

    await db.execute(f'''
        CREATE UNIQUE INDEX IF NOT EXISTS category_templates_one_active
        ON "{schema}".category_templates(guild_id)
        WHERE is_active = TRUE
    ''')

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".announcement_mirrors (
            guild_id BIGINT NOT NULL,
            associate_user_id BIGINT NOT NULL,
            source_channel_id BIGINT NOT NULL,
            source_message_id BIGINT NOT NULL,
            target_channel_id BIGINT NOT NULL,
            target_message_id BIGINT NOT NULL,
            join_message_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (guild_id, source_message_id)
        )
    ''')

    await db.execute(
        f'ALTER TABLE "{schema}".announcement_mirrors '
        'ADD COLUMN IF NOT EXISTS join_message_id BIGINT'
    )

    await db.execute(f'''
        CREATE TABLE IF NOT EXISTS "{schema}".audit_logs (
            log_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            actor_id BIGINT NOT NULL,
            associate_user_id BIGINT,
            community_name TEXT,
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (length(btrim(action)) BETWEEN 1 AND 100)
        )
    ''')

    await db.execute(f'''
        CREATE INDEX IF NOT EXISTS audit_logs_guild_created_idx
        ON "{schema}".audit_logs(guild_id, created_at DESC)
    ''')


async def add_allowed_role(db, schema: str, guild_id: int, role_id: int, added_by: int) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'''INSERT INTO "{schema}".allowed_roles (guild_id, role_id, added_by)
            VALUES ($1,$2,$3) ON CONFLICT DO NOTHING''',
        guild_id, role_id, added_by,
    )
    return not result.endswith(" 0")


async def remove_allowed_role(db, schema: str, guild_id: int, role_id: int) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'DELETE FROM "{schema}".allowed_roles WHERE guild_id=$1 AND role_id=$2',
        guild_id, role_id,
    )
    return not result.endswith(" 0")


async def list_allowed_roles(db, schema: str, guild_id: int) -> list[int]:
    schema = _schema_name(schema)
    rows = await db.fetch(
        f'SELECT role_id FROM "{schema}".allowed_roles WHERE guild_id=$1 ORDER BY created_at',
        guild_id,
    )
    return [int(r["role_id"]) for r in rows]


async def set_global_announcements_channel(
    db, schema: str, guild_id: int, channel_id: int | None, updated_by: int
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, global_announcements_channel_id, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                global_announcements_channel_id=EXCLUDED.global_announcements_channel_id,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, channel_id, updated_by,
    )


async def get_global_announcements_channel(db, schema: str, guild_id: int) -> int | None:
    schema = _schema_name(schema)
    return await db.fetchval(
        f'SELECT global_announcements_channel_id FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )


async def set_base_category(
    db, schema: str, guild_id: int, category_id: int | None, updated_by: int
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, base_category_id, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                base_category_id=EXCLUDED.base_category_id,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, category_id, updated_by,
    )


async def get_base_category(db, schema: str, guild_id: int) -> int | None:
    schema = _schema_name(schema)
    return await db.fetchval(
        f'SELECT base_category_id FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )


async def set_welcome_channel(
    db, schema: str, guild_id: int, channel_id: int | None, updated_by: int
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, welcome_channel_id, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                welcome_channel_id=EXCLUDED.welcome_channel_id,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, channel_id, updated_by,
    )


async def get_welcome_channel(db, schema: str, guild_id: int) -> int | None:
    schema = _schema_name(schema)
    return await db.fetchval(
        f'SELECT welcome_channel_id FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )


async def set_welcome_color(
    db, schema: str, guild_id: int, color_hex: str, updated_by: int
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, welcome_color_hex, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                welcome_color_hex=EXCLUDED.welcome_color_hex,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, color_hex, updated_by,
    )


async def get_welcome_color(db, schema: str, guild_id: int) -> str:
    schema = _schema_name(schema)
    value = await db.fetchval(
        f'SELECT welcome_color_hex FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )
    return str(value or "#57F287")


async def set_community_button_style(
    db,
    schema: str,
    guild_id: int,
    style: str,
    updated_by: int,
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, community_button_style, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                community_button_style=EXCLUDED.community_button_style,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, style, updated_by,
    )


async def get_community_button_style(
    db,
    schema: str,
    guild_id: int,
) -> str:
    schema = _schema_name(schema)
    value = await db.fetchval(
        f'SELECT community_button_style FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )
    return str(value or "secondary")


async def set_welcome_button_style(
    db, schema: str, guild_id: int, style: str, updated_by: int
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, welcome_button_style, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                welcome_button_style=EXCLUDED.welcome_button_style,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, style, updated_by,
    )


async def get_welcome_button_style(db, schema: str, guild_id: int) -> str:
    schema = _schema_name(schema)
    value = await db.fetchval(
        f'SELECT welcome_button_style FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )
    return str(value or "success")


async def set_announcement_button_style(
    db, schema: str, guild_id: int, style: str, updated_by: int
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id, announcement_button_style, updated_by)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE SET
                announcement_button_style=EXCLUDED.announcement_button_style,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, style, updated_by,
    )


async def get_announcement_button_style(db, schema: str, guild_id: int) -> str:
    schema = _schema_name(schema)
    value = await db.fetchval(
        f'SELECT announcement_button_style FROM "{schema}".settings WHERE guild_id=$1',
        guild_id,
    )
    return str(value or "secondary")


async def set_onboarding_prompt_config(
    db,
    schema: str,
    guild_id: int,
    prompt_id: int,
    prompt_title: str,
    updated_by: int,
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".settings
            (guild_id,onboarding_prompt_id,onboarding_prompt_title,updated_by)
            VALUES ($1,$2,$3,$4)
            ON CONFLICT (guild_id) DO UPDATE SET
                onboarding_prompt_id=EXCLUDED.onboarding_prompt_id,
                onboarding_prompt_title=EXCLUDED.onboarding_prompt_title,
                updated_by=EXCLUDED.updated_by,
                updated_at=NOW()''',
        guild_id, prompt_id, prompt_title, updated_by,
    )


async def get_onboarding_prompt_config(
    db,
    schema: str,
    guild_id: int,
):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT onboarding_prompt_id,onboarding_prompt_title
            FROM "{schema}".settings
            WHERE guild_id=$1''',
        guild_id,
    )


async def create_associate(
    db, schema: str, guild_id: int, user_id: int,
    display_name: str, community_name: str, added_by: int
) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'''INSERT INTO "{schema}".associates
            (guild_id,user_id,display_name,community_name,added_by)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (guild_id,user_id) DO NOTHING''',
        guild_id, user_id, display_name.strip(), community_name.strip(), added_by,
    )
    return not result.endswith(" 0")


async def get_associate(db, schema: str, guild_id: int, user_id: int):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'SELECT * FROM "{schema}".associates WHERE guild_id=$1 AND user_id=$2',
        guild_id, user_id,
    )


async def get_associate_by_community(db, schema: str, guild_id: int, community_name: str):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT * FROM "{schema}".associates
            WHERE guild_id=$1 AND lower(community_name)=lower($2)''',
        guild_id, community_name.strip(),
    )


async def list_associates(db, schema: str, guild_id: int):
    schema = _schema_name(schema)
    return await db.fetch(
        f'''SELECT
                a.*,
                s.category_id,
                s.integration_role_id,
                s.staff_role_id,
                s.status,
                s.template_version
            FROM "{schema}".associates a
            LEFT JOIN "{schema}".associate_spaces s
              ON s.guild_id=a.guild_id AND s.associate_user_id=a.user_id
            WHERE a.guild_id=$1
            ORDER BY lower(a.community_name), a.user_id''',
        guild_id,
    )


async def update_associate_community_role(
    db, schema: str, guild_id: int, user_id: int, role_id: int
) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'''UPDATE "{schema}".associates
            SET community_role_id=$3, updated_at=NOW()
            WHERE guild_id=$1 AND user_id=$2''',
        guild_id, user_id, role_id,
    )
    return not result.endswith(" 0")


async def delete_associate_record(db, schema: str, guild_id: int, user_id: int) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'DELETE FROM "{schema}".associates WHERE guild_id=$1 AND user_id=$2',
        guild_id, user_id,
    )
    return not result.endswith(" 0")


async def save_associate_space(
    db, schema: str, guild_id: int, associate_user_id: int,
    category_id: int | None = None,
    community_role_id: int | None = None,
    integration_role_id: int | None = None,
    staff_role_id: int | None = None,
    template_id: int | None = None,
    template_version: int | None = None,
    welcome_channel_id: int | None = None,
    welcome_message_id: int | None = None,
    status: str = "creating",
) -> None:
    schema = _schema_name(schema)
    if status not in {"creating", "active", "deleting", "error"}:
        raise ValueError("Estado Society no válido.")
    await db.execute(
        f'''INSERT INTO "{schema}".associate_spaces
            (guild_id,associate_user_id,category_id,community_role_id,
             integration_role_id,staff_role_id,template_id,template_version,
             welcome_channel_id,welcome_message_id,status)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (guild_id,associate_user_id) DO UPDATE SET
                category_id=COALESCE(EXCLUDED.category_id, "{schema}".associate_spaces.category_id),
                community_role_id=COALESCE(EXCLUDED.community_role_id, "{schema}".associate_spaces.community_role_id),
                integration_role_id=COALESCE(EXCLUDED.integration_role_id, "{schema}".associate_spaces.integration_role_id),
                staff_role_id=COALESCE(EXCLUDED.staff_role_id, "{schema}".associate_spaces.staff_role_id),
                template_id=COALESCE(EXCLUDED.template_id, "{schema}".associate_spaces.template_id),
                template_version=COALESCE(EXCLUDED.template_version, "{schema}".associate_spaces.template_version),
                welcome_channel_id=COALESCE(EXCLUDED.welcome_channel_id, "{schema}".associate_spaces.welcome_channel_id),
                welcome_message_id=COALESCE(EXCLUDED.welcome_message_id, "{schema}".associate_spaces.welcome_message_id),
                status=EXCLUDED.status,
                updated_at=NOW()''',
        guild_id, associate_user_id, category_id, community_role_id,
        integration_role_id, staff_role_id, template_id, template_version,
        welcome_channel_id, welcome_message_id, status,
    )


async def get_associate_space(db, schema: str, guild_id: int, associate_user_id: int):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT * FROM "{schema}".associate_spaces
            WHERE guild_id=$1 AND associate_user_id=$2''',
        guild_id, associate_user_id,
    )


async def set_associate_space_status(
    db, schema: str, guild_id: int, associate_user_id: int, status: str
) -> bool:
    schema = _schema_name(schema)
    if status not in {"creating", "active", "deleting", "error"}:
        raise ValueError("Estado Society no válido.")
    result = await db.execute(
        f'''UPDATE "{schema}".associate_spaces
            SET status=$3, updated_at=NOW()
            WHERE guild_id=$1 AND associate_user_id=$2''',
        guild_id, associate_user_id, status,
    )
    return not result.endswith(" 0")


async def save_associate_channel(
    db, schema: str, guild_id: int, associate_user_id: int,
    channel_id: int, channel_key: str, channel_type: str,
    is_template: bool = True
) -> None:
    """Guarda un binding de canal reemplazando IDs obsoletos por key lógica."""
    schema = _schema_name(schema)

    async with db.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                f'''DELETE FROM "{schema}".associate_channels
                    WHERE guild_id=$1
                      AND (
                        channel_id=$3
                        OR (associate_user_id=$2 AND channel_key=$4)
                      )''',
                guild_id, associate_user_id, channel_id, channel_key,
            )

            await connection.execute(
                f'''INSERT INTO "{schema}".associate_channels
                    (guild_id,associate_user_id,channel_id,channel_key,channel_type,is_template)
                    VALUES ($1,$2,$3,$4,$5,$6)''',
                guild_id, associate_user_id, channel_id, channel_key, channel_type, is_template,
            )


async def list_associate_channels(db, schema: str, guild_id: int, associate_user_id: int):
    schema = _schema_name(schema)
    return await db.fetch(
        f'''SELECT * FROM "{schema}".associate_channels
            WHERE guild_id=$1 AND associate_user_id=$2
            ORDER BY created_at, channel_id''',
        guild_id, associate_user_id,
    )


async def get_associate_channel(db, schema: str, guild_id: int, channel_id: int):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT * FROM "{schema}".associate_channels
            WHERE guild_id=$1 AND channel_id=$2''',
        guild_id, channel_id,
    )


async def delete_associate_channel_record(db, schema: str, guild_id: int, channel_id: int) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'DELETE FROM "{schema}".associate_channels WHERE guild_id=$1 AND channel_id=$2',
        guild_id, channel_id,
    )
    return not result.endswith(" 0")


async def find_associate_by_announcement_channel(db, schema: str, guild_id: int, channel_id: int):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT a.user_id, a.display_name, a.community_name, a.community_role_id
            FROM "{schema}".associate_channels c
            JOIN "{schema}".associates a
              ON a.guild_id=c.guild_id AND a.user_id=c.associate_user_id
            JOIN "{schema}".associate_spaces s
              ON s.guild_id=c.guild_id AND s.associate_user_id=c.associate_user_id
            WHERE c.guild_id=$1 AND c.channel_id=$2
              AND c.channel_type='ANN' AND s.status='active' ''',
        guild_id, channel_id,
    )


async def get_community_entry_channel_id(
    db, schema: str, guild_id: int, associate_user_id: int
) -> int | None:
    schema = _schema_name(schema)
    return await db.fetchval(
        f'''SELECT channel_id
            FROM "{schema}".associate_channels
            WHERE guild_id=$1 AND associate_user_id=$2
              AND channel_type='TXT'
            ORDER BY CASE WHEN channel_key='txt_01' THEN 0 ELSE 1 END, created_at
            LIMIT 1''',
        guild_id, associate_user_id,
    )


async def list_active_role_button_bindings(db, schema: str, guild_id: int):
    schema = _schema_name(schema)
    return await db.fetch(
        f'''SELECT
                s.associate_user_id,
                s.community_role_id,
                s.welcome_channel_id,
                s.welcome_message_id,
                a.community_name,
                (
                    SELECT c.channel_id
                    FROM "{schema}".associate_channels c
                    WHERE c.guild_id=s.guild_id
                      AND c.associate_user_id=s.associate_user_id
                      AND c.channel_type='TXT'
                    ORDER BY CASE WHEN c.channel_key='txt_01' THEN 0 ELSE 1 END, c.created_at
                    LIMIT 1
                ) AS entry_channel_id
            FROM "{schema}".associate_spaces s
            JOIN "{schema}".associates a
              ON a.guild_id=s.guild_id AND a.user_id=s.associate_user_id
            WHERE s.guild_id=$1 AND s.status='active'
              AND s.community_role_id IS NOT NULL
              AND s.welcome_message_id IS NOT NULL''',
        guild_id,
    )


async def get_next_template_version(db, schema: str, guild_id: int) -> int:
    schema = _schema_name(schema)
    value = await db.fetchval(
        f'SELECT COALESCE(MAX(version),0)+1 FROM "{schema}".category_templates WHERE guild_id=$1',
        guild_id,
    )
    return int(value or 1)


async def create_template(
    db, schema: str, guild_id: int, name: str, version: int,
    raw_template: str, parsed_template: dict[str, Any],
    uploaded_by: int, activate: bool = True
) -> int:
    schema = _schema_name(schema)
    parsed_json = json.dumps(parsed_template, ensure_ascii=False)
    async with db.acquire() as conn:
        async with conn.transaction():
            if activate:
                await conn.execute(
                    f'UPDATE "{schema}".category_templates SET is_active=FALSE WHERE guild_id=$1',
                    guild_id,
                )
            template_id = await conn.fetchval(
                f'''INSERT INTO "{schema}".category_templates
                    (guild_id,name,version,raw_template,parsed_template,is_active,uploaded_by)
                    VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7)
                    RETURNING template_id''',
                guild_id, name.strip(), version, raw_template, parsed_json, activate, uploaded_by,
            )
    return int(template_id)


async def get_active_template(db, schema: str, guild_id: int):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT * FROM "{schema}".category_templates
            WHERE guild_id=$1 AND is_active=TRUE LIMIT 1''',
        guild_id,
    )


async def list_templates(db, schema: str, guild_id: int):
    schema = _schema_name(schema)
    return await db.fetch(
        f'''SELECT template_id,name,version,is_active,uploaded_by,created_at
            FROM "{schema}".category_templates
            WHERE guild_id=$1 ORDER BY version DESC''',
        guild_id,
    )


async def save_announcement_mirror(
    db, schema: str, guild_id: int, associate_user_id: int,
    source_channel_id: int, source_message_id: int,
    target_channel_id: int, target_message_id: int,
    join_message_id: int | None = None,
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''INSERT INTO "{schema}".announcement_mirrors
            (guild_id,associate_user_id,source_channel_id,source_message_id,
             target_channel_id,target_message_id,join_message_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (guild_id,source_message_id) DO UPDATE SET
                associate_user_id=EXCLUDED.associate_user_id,
                source_channel_id=EXCLUDED.source_channel_id,
                target_channel_id=EXCLUDED.target_channel_id,
                target_message_id=EXCLUDED.target_message_id,
                join_message_id=EXCLUDED.join_message_id,
                created_at=NOW()''',
        guild_id, associate_user_id, source_channel_id, source_message_id,
        target_channel_id, target_message_id, join_message_id,
    )


async def get_announcement_mirror(db, schema: str, guild_id: int, source_message_id: int):
    schema = _schema_name(schema)
    return await db.fetchrow(
        f'''SELECT * FROM "{schema}".announcement_mirrors
            WHERE guild_id=$1 AND source_message_id=$2''',
        guild_id, source_message_id,
    )



async def list_announcement_ctas_for_associate(
    db,
    schema: str,
    guild_id: int,
    associate_user_id: int,
    *,
    exclude_source_message_id: int | None = None,
):
    schema = _schema_name(schema)

    if exclude_source_message_id is None:
        return await db.fetch(
            f'''SELECT *
                FROM "{schema}".announcement_mirrors
                WHERE guild_id=$1
                  AND associate_user_id=$2
                  AND join_message_id IS NOT NULL
                ORDER BY created_at DESC, source_message_id DESC''',
            guild_id,
            associate_user_id,
        )

    return await db.fetch(
        f'''SELECT *
            FROM "{schema}".announcement_mirrors
            WHERE guild_id=$1
              AND associate_user_id=$2
              AND join_message_id IS NOT NULL
              AND source_message_id<>$3
            ORDER BY created_at DESC, source_message_id DESC''',
        guild_id,
        associate_user_id,
        exclude_source_message_id,
    )


async def clear_announcement_join_message(
    db,
    schema: str,
    guild_id: int,
    source_message_id: int,
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''UPDATE "{schema}".announcement_mirrors
            SET join_message_id=NULL
            WHERE guild_id=$1 AND source_message_id=$2''',
        guild_id,
        source_message_id,
    )


async def set_announcement_join_message(
    db,
    schema: str,
    guild_id: int,
    source_message_id: int,
    join_message_id: int | None,
) -> None:
    schema = _schema_name(schema)
    await db.execute(
        f'''UPDATE "{schema}".announcement_mirrors
            SET join_message_id=$3
            WHERE guild_id=$1 AND source_message_id=$2''',
        guild_id,
        source_message_id,
        join_message_id,
    )


async def list_recent_announcement_mirrors_for_associate(
    db,
    schema: str,
    guild_id: int,
    associate_user_id: int,
):
    schema = _schema_name(schema)
    return await db.fetch(
        f'''SELECT *
            FROM "{schema}".announcement_mirrors
            WHERE guild_id=$1 AND associate_user_id=$2
            ORDER BY created_at DESC, source_message_id DESC''',
        guild_id,
        associate_user_id,
    )


async def list_active_announcement_role_button_bindings(
    db,
    schema: str,
    guild_id: int,
):
    schema = _schema_name(schema)
    return await db.fetch(
        f'''SELECT
                m.source_message_id,
                m.target_channel_id,
                m.join_message_id,
                m.associate_user_id,
                s.community_role_id,
                a.community_name,
                (
                    SELECT c.channel_id
                    FROM "{schema}".associate_channels c
                    WHERE c.guild_id=m.guild_id
                      AND c.associate_user_id=m.associate_user_id
                      AND c.channel_type='TXT'
                    ORDER BY
                        CASE WHEN c.channel_key='txt_01' THEN 0 ELSE 1 END,
                        c.created_at
                    LIMIT 1
                ) AS entry_channel_id
            FROM "{schema}".announcement_mirrors m
            JOIN "{schema}".associate_spaces s
              ON s.guild_id=m.guild_id
             AND s.associate_user_id=m.associate_user_id
            JOIN "{schema}".associates a
              ON a.guild_id=m.guild_id
             AND a.user_id=m.associate_user_id
            WHERE m.guild_id=$1
              AND m.join_message_id IS NOT NULL
              AND s.status='active'
              AND s.community_role_id IS NOT NULL
            ORDER BY m.associate_user_id, m.created_at DESC, m.source_message_id DESC''',
        guild_id,
    )


async def delete_announcement_mirror(db, schema: str, guild_id: int, source_message_id: int) -> bool:
    schema = _schema_name(schema)
    result = await db.execute(
        f'DELETE FROM "{schema}".announcement_mirrors WHERE guild_id=$1 AND source_message_id=$2',
        guild_id, source_message_id,
    )
    return not result.endswith(" 0")


async def add_audit_log(
    db, schema: str, guild_id: int, action: str, actor_id: int,
    associate_user_id: int | None = None,
    community_name: str | None = None,
    metadata: dict[str, Any] | None = None
) -> int:
    schema = _schema_name(schema)
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else None
    log_id = await db.fetchval(
        f'''INSERT INTO "{schema}".audit_logs
            (guild_id,action,actor_id,associate_user_id,community_name,metadata)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb)
            RETURNING log_id''',
        guild_id, action.strip(), actor_id, associate_user_id, community_name, metadata_json,
    )
    return int(log_id)


async def vexmod_role_transfers_available(db, vexmod_schema: str) -> bool:
    vexmod_schema = _schema_name(vexmod_schema)
    relation = await db.fetchval("SELECT to_regclass($1)", f"{vexmod_schema}.role_transfers")
    return relation is not None


async def upsert_vexmod_role_transfer(
    db, vexmod_schema: str, guild_id: int,
    onboarding_role_id: int, verified_role_id: int,
    name: str, configured_by: int
) -> None:
    vexmod_schema = _schema_name(vexmod_schema)
    if onboarding_role_id == verified_role_id:
        raise ValueError("El rol INT y el rol definitivo no pueden ser iguales.")
    if not await vexmod_role_transfers_available(db, vexmod_schema):
        raise RuntimeError(f"No existe {vexmod_schema}.role_transfers.")
    await db.execute(
        f'''INSERT INTO "{vexmod_schema}".role_transfers
            (guild_id,onboarding_role_id,verified_role_id,name,configured_by)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (guild_id,onboarding_role_id) DO UPDATE SET
                verified_role_id=EXCLUDED.verified_role_id,
                name=EXCLUDED.name,
                configured_by=EXCLUDED.configured_by,
                updated_at=NOW()''',
        guild_id, onboarding_role_id, verified_role_id, name.strip(), configured_by,
    )


async def delete_vexmod_role_transfer(
    db, vexmod_schema: str, guild_id: int, onboarding_role_id: int
) -> bool:
    vexmod_schema = _schema_name(vexmod_schema)
    if not await vexmod_role_transfers_available(db, vexmod_schema):
        raise RuntimeError(f"No existe {vexmod_schema}.role_transfers.")
    result = await db.execute(
        f'DELETE FROM "{vexmod_schema}".role_transfers WHERE guild_id=$1 AND onboarding_role_id=$2',
        guild_id, onboarding_role_id,
    )
    return not result.endswith(" 0")
