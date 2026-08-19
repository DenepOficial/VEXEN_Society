from __future__ import annotations

import re

DEFAULT_WELCOME_COLOR_HEX = "#57F287"
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-F]{6}$")


def normalize_welcome_color(value: str) -> str:
    """Normaliza un color de bienvenida a #RRGGBB.

    Acepta ``default``, ``#57F287`` o ``57F287``.
    """
    value = value.strip()

    if not value:
        raise ValueError("El color no puede estar vacío.")

    if value.casefold() == "default":
        return DEFAULT_WELCOME_COLOR_HEX

    if not value.startswith("#"):
        value = f"#{value}"

    value = value.upper()

    if not _HEX_COLOR_PATTERN.fullmatch(value):
        raise ValueError(
            "Color inválido. Usa #RRGGBB, por ejemplo #57F287, o 'default'."
        )

    return value


def welcome_color_to_int(value: str) -> int:
    normalized = normalize_welcome_color(value)
    return int(normalized[1:], 16)
