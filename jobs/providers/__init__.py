from typing import Any, Dict, List

from jobs.filters import matches_level_filter, normalize_allowed_levels
from jobs.providers.common import dedupe_offers
from jobs.providers.isitfair import collect_offers


def fetch_matching_offers(filters: Dict[str, Any], max_pages: int) -> List[Dict[str, Any]]:
    """Aggregate offers from all configured providers and apply shared filters."""
    offers = collect_offers(filters, max_pages)
    offers = dedupe_offers(offers)

    allowed_levels = normalize_allowed_levels(filters.get("allowed_levels"))
    return [offer for offer in offers if matches_level_filter(offer, allowed_levels)]
