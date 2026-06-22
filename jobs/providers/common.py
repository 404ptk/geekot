from typing import Any, Dict, List, Optional, Set

from jobs.constants import LOCAL_FILTER_KEYS


def api_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in filters.items()
        if key not in LOCAL_FILTER_KEYS and value is not None and value != ""
    }


def merge_search(*parts: Optional[str]) -> Optional[str]:
    tokens = [part.strip() for part in parts if part and part.strip()]
    return " ".join(tokens) if tokens else None


def dedupe_offers(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for offer in offers:
        offer_uuid = offer.get("offer_uuid")
        if not offer_uuid or offer_uuid in seen:
            continue
        seen.add(offer_uuid)
        unique.append(offer)
    return unique


def offer_id(offer: Dict[str, Any], provider: str = "isitfair") -> Optional[str]:
    raw_id = offer.get("offer_uuid")
    if not raw_id:
        return None
    return f"{provider}:{raw_id}"
