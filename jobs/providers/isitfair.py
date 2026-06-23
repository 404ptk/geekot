import requests

from jobs.filters import matches_city, is_fully_remote
from jobs.providers.common import api_filters, merge_search
from jobs.providers.sources import company_logo_url, source_label

API_BASE_URL = "https://isitfair.pl/api/v1/offers/search"
USER_AGENT = {"User-Agent": "geekot-bot/1.0 (+discord jobs watcher)"}


def build_params(filters, page: int, search: str = None):
    params = {"page": page}
    remote_api_filters = api_filters(filters)
    for key in ("offer_status", "offer_source", "offer_category"):
        value = remote_api_filters.get(key)
        if value:
            params[key] = value

    merged_search = search if search is not None else remote_api_filters.get("search")
    if merged_search:
        params["search"] = merged_search
    return params


def fetch_offers_page(filters, page: int, search: str = None):
    try:
        response = requests.get(
            API_BASE_URL,
            params=build_params(filters, page, search=search),
            headers=USER_AGENT,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) if isinstance(payload, dict) else []
    except Exception as e:
        print(f"[Jobs][IsItFair] API error (page {page}): {e}")
        return []


def fetch_offers(filters, max_pages: int, search: str = None):
    offers = []
    for page in range(1, max_pages + 1):
        page_offers = fetch_offers_page(filters, page, search=search)
        if not page_offers:
            break
        offers.extend(page_offers)
    return offers


def collect_offers(filters, max_pages: int):
    location_city = filters.get("location_city")
    include_remote = bool(filters.get("include_remote"))
    user_search = api_filters(filters).get("search")
    collected = []

    if location_city:
        city_search = merge_search(user_search, location_city)
        city_offers = fetch_offers(filters, max_pages, search=city_search)
        collected.extend(offer for offer in city_offers if matches_city(offer, location_city))

    if include_remote:
        remote_search = merge_search(user_search, "remote")
        remote_offers = fetch_offers(filters, max_pages, search=remote_search)
        collected.extend(offer for offer in remote_offers if is_fully_remote(offer))

    if not location_city and not include_remote:
        collected.extend(fetch_offers(filters, max_pages))

    return collected


