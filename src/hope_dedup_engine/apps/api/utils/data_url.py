from typing import NamedTuple, Literal


class ParsedDataURL(NamedTuple):
    mimetype: str | None
    encoding: Literal["base64"] | None
    content: str


def parse_data_url(content: str) -> ParsedDataURL | None:
    parts = content.split(";", 1)
    if len(parts) != 2:
        return None

    header, body = parts

    header_parts = header.split(":", maxsplit=1)
    if len(header_parts) != 2:
        return None

    if header_parts[0].lower() != "data":
        return None

    mimetype = stripped if (stripped := header_parts[1].strip()) else None

    body_parts = body.split(",", maxsplit=1)
    if len(body_parts) == 1:
        encoding = None
        content = body_parts[0].strip()
    else:
        encoding = stripped if (stripped := body_parts[0].strip()) and stripped.lower() == "base64" else None
        if encoding is None:
            content = body.strip()
        else:
            content = body_parts[1].strip()

    return ParsedDataURL(
        mimetype=mimetype,
        encoding="base64" if encoding else None,
        content=content,
    )


def inline_label(value: str) -> str:
    parsed = parse_data_url(value)
    if not parsed or parsed.encoding != "base64":
        return value

    mime = (parsed.mimetype or "application/octet-stream").lower()
    return f"{mime}:<binary-data>"
