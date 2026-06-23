from datetime import datetime
from typing import Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

POLISH_MONTHS = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)


def parse_published_at(value: str) -> Optional[datetime]:
    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        if cleaned.endswith("Z"):
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass

    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern)
        except ValueError:
            continue
    return None


def format_published_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    parsed = parse_published_at(value)
    if not parsed:
        return value

    return f"{parsed.day} {POLISH_MONTHS[parsed.month - 1]}"


def sanitize_url(url: Optional[str]) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None

    cleaned = url.strip()
    if not cleaned.startswith(("http://", "https://")):
        return None

    try:
        parts = urlsplit(cleaned)
        if not parts.netloc:
            return None

        path = quote(unquote(parts.path), safe="/")
        query = quote(unquote(parts.query), safe="=&?/:") if parts.query else parts.query
        fragment = quote(unquote(parts.fragment), safe="") if parts.fragment else parts.fragment
        return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))
    except Exception:
        return None
