from typing import Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit


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
