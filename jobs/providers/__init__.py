from typing import Any, Dict, List

from jobs.filters import matches_level_filter, normalize_allowed_levels
from jobs.providers.common import dedupe_offers
from jobs.providers.isitfair import collect_offers as collect_isitfair_offers
from jobs.providers.olx import OFFER_SOURCE as OLX_SOURCE
from jobs.providers.olx import collect_offers as collect_olx_offers


def fetch_matching_offers(filters: Dict[str, Any], max_pages: int) -> List[Dict[str, Any]]:
    """Aggregate offers from all configured providers and apply shared filters."""
    selected_source = filters.get("offer_source")
    offers: List[Dict[str, Any]] = []

    if not selected_source or selected_source != OLX_SOURCE:
        offers.extend(collect_isitfair_offers(filters, max_pages))
    if not selected_source or selected_source == OLX_SOURCE:
        offers.extend(collect_olx_offers(filters, max_pages))

    offers = dedupe_offers(offers)

    allowed_levels = normalize_allowed_levels(filters.get("allowed_levels"))
    return [offer for offer in offers if matches_level_filter(offer, allowed_levels)]
