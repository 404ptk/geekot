import re
import unicodedata
from typing import Any, Dict, List, Optional

from jobs.constants import (
    ALL_LEVELS,
    DEFAULT_ALLOWED_LEVELS,
    LEVEL_LABELS,
    LEVEL_PATTERNS,
)


def detect_offer_level(offer: Dict[str, Any]) -> Optional[str]:
    title = (offer.get("offer_title") or "").casefold()
    for level in ("internship", "junior", "senior", "mid"):
        for pattern in LEVEL_PATTERNS[level]:
            if re.search(pattern, title):
                return level
    return None


def matches_level_filter(offer: Dict[str, Any], allowed_levels: List[str]) -> bool:
    detected = detect_offer_level(offer)
    if detected is None:
        return True
    return detected in allowed_levels


def normalize_allowed_levels(levels: Optional[List[str]]) -> List[str]:
    if not levels:
        return list(DEFAULT_ALLOWED_LEVELS)
    return [level for level in ALL_LEVELS if level in levels]


def update_allowed_levels(filters: Dict[str, Any], **toggles: Optional[bool]) -> List[str]:
    allowed = set(normalize_allowed_levels(filters.get("allowed_levels")))
    for level, enabled in toggles.items():
        if enabled is None:
            continue
        if enabled:
            allowed.add(level)
        else:
            allowed.discard(level)
    normalized = [level for level in ALL_LEVELS if level in allowed]
    filters["allowed_levels"] = normalized
    return normalized


def normalize_location(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )


def matches_city(offer: Dict[str, Any], location_city: str) -> bool:
    city = offer.get("offer_city") or ""
    return normalize_location(location_city) in normalize_location(city)


def is_fully_remote(offer: Dict[str, Any]) -> bool:
    return (offer.get("offer_city") or "").casefold() == "remote"


def location_summary(filters: Dict[str, Any]) -> str:
    location_city = filters.get("location_city")
    include_remote = bool(filters.get("include_remote"))

    if location_city and include_remote:
        return f"{location_city} lub w pełni zdalne"
    if location_city:
        return str(location_city)
    if include_remote:
        return "tylko w pełni zdalne"
    return "wszystkie"


def levels_summary(filters: Dict[str, Any]) -> str:
    allowed = normalize_allowed_levels(filters.get("allowed_levels"))
    labels = [LEVEL_LABELS[level] for level in allowed]
    disabled = [LEVEL_LABELS[level] for level in ALL_LEVELS if level not in allowed]
    text = ", ".join(labels) if labels else "brak"
    if disabled:
        text += f"\nWyłączone: {', '.join(disabled)}"
    text += "\nOferty bez rozpoznanego poziomu: zawsze dozwolone"
    return text


def filters_summary(filters: Dict[str, Any]) -> str:
    lines = [
        f"**Status:** {filters.get('offer_status', 'active')}",
        f"**Lokalizacja:** {location_summary(filters)}",
        f"**Poziom:** {', '.join(LEVEL_LABELS[level] for level in normalize_allowed_levels(filters.get('allowed_levels')))}",
        f"**Źródło:** {filters.get('offer_source') or 'wszystkie'}",
        f"**Kategoria:** {filters.get('offer_category') or 'wszystkie'}",
        f"**Szukaj:** {filters.get('search') or '—'}",
    ]
    return "\n".join(lines)
