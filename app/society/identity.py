from __future__ import annotations

from dataclasses import dataclass
import re


CUSTOM_EMOJI_PATTERN = re.compile(
    r"<a?:[A-Za-z0-9_~]+:\d{15,25}>"
)


@dataclass(frozen=True, slots=True)
class SocietyDisplayIdentity:
    raw: str
    text: str
    custom_emoji: str | None


def parse_society_display_identity(value: str) -> SocietyDisplayIdentity:
    """
    Conserva el valor original, pero separa el primer emoji personalizado
    de Discord del texto visible.

    Ejemplo:
      <:logo:1538690277991120938> Prueba
    se convierte en:
      text = "Prueba"
      custom_emoji = "<:logo:1538690277991120938>"
    """
    raw = value.strip()
    matches = list(CUSTOM_EMOJI_PATTERN.finditer(raw))
    custom_emoji = matches[0].group(0) if matches else None

    text = CUSTOM_EMOJI_PATTERN.sub("", raw)
    text = " ".join(text.split()).strip()

    return SocietyDisplayIdentity(
        raw=raw,
        text=text,
        custom_emoji=custom_emoji,
    )
