from __future__ import annotations

DEFAULT_WELCOME_BUTTON_STYLE = "success"
DEFAULT_ANNOUNCEMENT_BUTTON_STYLE = "secondary"
DEFAULT_COMMUNITY_BUTTON_STYLE = DEFAULT_ANNOUNCEMENT_BUTTON_STYLE

COMMUNITY_BUTTON_STYLES: dict[str, str] = {
    "primary": "Azul",
    "secondary": "Gris / oscuro",
    "success": "Verde",
    "danger": "Rojo",
}


def normalize_community_button_style(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in COMMUNITY_BUTTON_STYLES:
        allowed = ", ".join(COMMUNITY_BUTTON_STYLES)
        raise ValueError(f"Estilo inválido. Usa uno de estos nombres: {allowed}.")
    return normalized


def community_button_style_label(value: str) -> str:
    normalized = normalize_community_button_style(value)
    return f"{normalized} — {COMMUNITY_BUTTON_STYLES[normalized]}"


def build_community_join_label(community_name: str, max_length: int = 80) -> str:
    prefix = "Unirme a "
    name = community_name.strip()
    label = f"{prefix}{name}"
    if len(label) <= max_length:
        return label
    available = max_length - len(prefix) - 1
    shortened = name[:max(1, available)].rstrip()
    return f"{prefix}{shortened}…"
