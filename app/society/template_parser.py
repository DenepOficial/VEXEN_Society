from __future__ import annotations

import re
from dataclasses import dataclass


CATEGORY_TYPE = "CATEGORY"
CHANNEL_TYPES = {"ANN", "TXT", "STAFF-TXT", "VOICE", "STAFF-VOICE"}
ALL_TYPES = {CATEGORY_TYPE, *CHANNEL_TYPES}

ASSOCIATE_VARIABLE = "{ asociado }"

# Discord custom emoji markup:
# <:nombre:123456789012345678>
# <a:nombre:123456789012345678>
_CUSTOM_EMOJI_PATTERN = re.compile(
    r"<a?:[A-Za-z0-9_~]+:\d{15,25}>"
)


def sanitize_associate_name_for_category(value: str) -> str:
    """
    Quita emojis personalizados de Discord únicamente del texto
    utilizado para el nombre de la categoría.

    El display_name original se conserva intacto para PostgreSQL y
    para Discord Onboarding.
    """
    cleaned = _CUSTOM_EMOJI_PATTERN.sub("", value)
    cleaned = " ".join(cleaned.split()).strip()

    if not cleaned:
        raise TemplateValidationError(
            "El nombre del asociado necesita texto además del emoji "
            "para poder crear la categoría."
        )

    return cleaned


COMMUNITY_VARIABLE = "{ comunidad }"
VXS_LITERAL = "{ VXS }"

ALLOWED_CATEGORY_BRACES = {VXS_LITERAL, ASSOCIATE_VARIABLE, COMMUNITY_VARIABLE}

MAX_CATEGORY_LENGTH = 100
MAX_CHANNEL_LENGTH = 100
MAX_TEMPLATE_CHANNELS = 49

_LINE_PATTERN = re.compile(r"^\[([A-Za-z-]+)\]\s+(.+)$")
_BRACE_PATTERN = re.compile(r"\{[^{}]+\}")
_ASSOCIATE_LOOSE_PATTERN = re.compile(r"\{\s*asociado\s*\}", re.IGNORECASE)
_COMMUNITY_LOOSE_PATTERN = re.compile(r"\{\s*comunidad\s*\}", re.IGNORECASE)


class TemplateValidationError(ValueError):
    def __init__(self, message: str, line_number: int | None = None) -> None:
        self.message = message
        self.line_number = line_number
        super().__init__(f"Línea {line_number}: {message}" if line_number else message)


@dataclass(frozen=True, slots=True)
class ChannelTemplate:
    channel_type: str
    name: str
    channel_key: str
    source_line: int

    def to_dict(self) -> dict:
        return {
            "type": self.channel_type,
            "name": self.name,
            "key": self.channel_key,
            "source_line": self.source_line,
        }


@dataclass(frozen=True, slots=True)
class ParsedTemplate:
    category_name: str
    channels: tuple[ChannelTemplate, ...]

    def to_dict(self) -> dict:
        return {
            "category": self.category_name,
            "channels": [c.to_dict() for c in self.channels],
        }

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    @property
    def announcement_channel(self) -> ChannelTemplate:
        for channel in self.channels:
            if channel.channel_type == "ANN":
                return channel
        raise RuntimeError("La plantilla no contiene canal ANN.")


def parsed_template_from_dict(data: dict) -> ParsedTemplate:
    return ParsedTemplate(
        category_name=str(data["category"]),
        channels=tuple(
            ChannelTemplate(
                channel_type=str(item["type"]),
                name=str(item["name"]),
                channel_key=str(item["key"]),
                source_line=int(item.get("source_line", 0)),
            )
            for item in data["channels"]
        ),
    )


def _validate_exact_variables(category_name: str, line_number: int) -> None:
    match = _ASSOCIATE_LOOSE_PATTERN.search(category_name)
    if match and ASSOCIATE_VARIABLE not in category_name:
        raise TemplateValidationError(
            "La variable de asociado debe escribirse exactamente como: { asociado }",
            line_number,
        )

    match = _COMMUNITY_LOOSE_PATTERN.search(category_name)
    if match and COMMUNITY_VARIABLE not in category_name:
        raise TemplateValidationError(
            "La variable de comunidad debe escribirse exactamente como: { comunidad }",
            line_number,
        )

    if category_name.count(ASSOCIATE_VARIABLE) != 1:
        raise TemplateValidationError(
            "La categoría debe contener exactamente una vez { asociado }.",
            line_number,
        )

    if category_name.count(COMMUNITY_VARIABLE) != 1:
        raise TemplateValidationError(
            "La categoría debe contener exactamente una vez { comunidad }.",
            line_number,
        )


def _validate_category_braces(category_name: str, line_number: int) -> None:
    for brace in _BRACE_PATTERN.findall(category_name):
        if brace not in ALLOWED_CATEGORY_BRACES:
            raise TemplateValidationError(
                f"Bloque entre llaves no reconocido: {brace}",
                line_number,
            )

    cleaned = category_name
    for allowed in ALLOWED_CATEGORY_BRACES:
        cleaned = cleaned.replace(allowed, "")

    if "{" in cleaned or "}" in cleaned:
        raise TemplateValidationError(
            "La categoría contiene llaves inválidas o incompletas.",
            line_number,
        )


def parse_template(raw_template: str) -> ParsedTemplate:
    if not isinstance(raw_template, str) or not raw_template.strip():
        raise TemplateValidationError("La plantilla está vacía.")

    category_name: str | None = None
    channels: list[ChannelTemplate] = []
    used_names: set[str] = set()
    counters: dict[str, int] = {}
    announcement_count = 0

    for line_number, original_line in enumerate(raw_template.splitlines(), start=1):
        line = original_line.strip()

        if not line or line.startswith("#"):
            continue

        match = _LINE_PATTERN.fullmatch(line)
        if not match:
            raise TemplateValidationError(
                "Formato inválido. Se esperaba [TIPO] nombre.",
                line_number,
            )

        item_type = match.group(1).upper()
        item_name = match.group(2).strip()

        if item_type not in ALL_TYPES:
            raise TemplateValidationError(
                f"Tipo desconocido [{item_type}]. Tipos válidos: "
                + ", ".join(sorted(ALL_TYPES)),
                line_number,
            )

        if item_type == CATEGORY_TYPE:
            if category_name is not None:
                raise TemplateValidationError(
                    "Solo puede existir una [CATEGORY].",
                    line_number,
                )
            if len(item_name) > MAX_CATEGORY_LENGTH:
                raise TemplateValidationError(
                    f"La categoría supera {MAX_CATEGORY_LENGTH} caracteres.",
                    line_number,
                )
            _validate_exact_variables(item_name, line_number)
            _validate_category_braces(item_name, line_number)
            category_name = item_name
            continue

        if len(channels) >= MAX_TEMPLATE_CHANNELS:
            raise TemplateValidationError(
                f"La plantilla supera {MAX_TEMPLATE_CHANNELS} canales.",
                line_number,
            )

        if len(item_name) > MAX_CHANNEL_LENGTH:
            raise TemplateValidationError(
                f"El canal supera {MAX_CHANNEL_LENGTH} caracteres.",
                line_number,
            )

        if "{" in item_name or "}" in item_name:
            raise TemplateValidationError(
                "Los canales no pueden contener variables entre llaves.",
                line_number,
            )

        normalized = item_name.casefold()
        if normalized in used_names:
            raise TemplateValidationError(
                f"Nombre de canal duplicado: {item_name}",
                line_number,
            )
        used_names.add(normalized)

        counters[item_type] = counters.get(item_type, 0) + 1

        if item_type == "ANN":
            announcement_count += 1
            if announcement_count > 1:
                raise TemplateValidationError(
                    "Solo puede existir un canal [ANN].",
                    line_number,
                )
            channel_key = "announcements"
        else:
            prefix = item_type.casefold().replace("-", "_")
            channel_key = f"{prefix}_{counters[item_type]:02d}"

        channels.append(
            ChannelTemplate(
                item_type,
                item_name,
                channel_key,
                line_number,
            )
        )

    if category_name is None:
        raise TemplateValidationError("Falta la línea [CATEGORY].")

    if not channels:
        raise TemplateValidationError("La plantilla debe contener al menos un canal.")

    if announcement_count != 1:
        raise TemplateValidationError(
            "La plantilla debe contener exactamente un canal [ANN]."
        )

    return ParsedTemplate(category_name, tuple(channels))


def render_category_name(
    parsed_template: ParsedTemplate,
    associate_name: str,
    community_name: str,
) -> str:
    associate_name = associate_name.strip()
    community_name = community_name.strip()

    if associate_name:
        associate_name = sanitize_associate_name_for_category(
            associate_name
        )

    if not associate_name or not community_name:
        raise TemplateValidationError("Asociado y comunidad son obligatorios.")

    if any(x in associate_name + community_name for x in "{}"):
        raise TemplateValidationError("Los nombres no pueden contener llaves.")

    result = parsed_template.category_name
    result = result.replace(
        ASSOCIATE_VARIABLE,
        f"{{ {associate_name} }}",
    )
    result = result.replace(
        COMMUNITY_VARIABLE,
        f"{{ {community_name} }}",
    )

    if len(result) > MAX_CATEGORY_LENGTH:
        raise TemplateValidationError(
            f"El nombre final de la categoría supera {MAX_CATEGORY_LENGTH} caracteres."
        )

    return result
