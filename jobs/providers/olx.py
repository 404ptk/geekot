from typing import Any, Dict, List, Optional

import requests

from jobs.filters import matches_city
from jobs.providers.common import api_filters, merge_search

API_BASE_URL = "https://www.olx.pl/api/v1/offers/"
IT_CATEGORY_ID = 56
OFFER_SOURCE = "olx.pl"
PAGE_SIZE = 40
USER_AGENT = {"User-Agent": "geekot-bot/1.0 (+discord jobs watcher)"}


def _param_value(offer: Dict[str, Any], key: str) -> Optional[Any]:
    for param in offer.get("params", []):
        if param.get("key") == key:
            return param.get("value")
    return None


def workplace_keys(offer: Dict[str, Any]) -> List[str]:
    value = _param_value(offer, "workplace")
    if not isinstance(value, dict):
        return []
    raw = value.get("key")
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if raw:
        return [str(raw)]
    return []


def is_fully_remote(offer: Dict[str, Any]) -> bool:
    keys = workplace_keys(offer)
    return keys == ["remote_work_possibility"]


def _city_name(offer: Dict[str, Any]) -> str:
    location = offer.get("location") or {}
    city = location.get("city") or {}
    return city.get("name") or ""


def _company_name(offer: Dict[str, Any]) -> str:
    user = offer.get("user") or {}
    company_name = (user.get("company_name") or "").strip()
    if company_name:
        return company_name
    user_name = (user.get("name") or "").strip()
    if user_name:
        return user_name
    return "Ogłoszeniodawca OLX"


def _salary_fields(offer: Dict[str, Any]) -> Dict[str, Any]:
    salary = _param_value(offer, "salary")
    if not isinstance(salary, dict):
        return {
            "offer_salary_qualifies": False,
        }

    salary_from = salary.get("from")
    salary_to = salary.get("to")
    if salary_from is None and salary_to is None:
        return {
            "offer_salary_qualifies": False,
        }

    currency = salary.get("currency") or "PLN"
    if currency != "PLN":
        return {
            "offer_salary_qualifies": False,
        }

    interval = salary.get("type") or "monthly"
    return {
        "offer_salary_qualifies": True,
        "offer_salary_min": salary_from or salary_to,
        "offer_salary_max": salary_to or salary_from,
        "offer_formatted_salary_min": salary_from or salary_to,
        "offer_formatted_salary_max": salary_to or salary_from,
        "offer_salary_interval": interval,
    }


def normalize_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    remote = is_fully_remote(offer)
    city = "Remote" if remote else _city_name(offer)
    normalized = {
        "offer_uuid": f"olx:{offer.get('id')}",
        "offer_title": offer.get("title") or "Nowa oferta pracy",
        "offer_href": offer.get("url"),
        "offer_city": city,
        "offer_category": "IT",
        "offer_source": OFFER_SOURCE,
        "offer_published_at": offer.get("created_time") or offer.get("last_refresh_time"),
        "offer_is_fair": False,
        "company": {
            "company_name": _company_name(offer),
        },
        "_olx_photos": offer.get("photos") or [],
        "_olx_user": offer.get("user") or {},
    }
    normalized.update(_salary_fields(offer))
    return normalized


def fetch_offers_page(query: Optional[str], offset: int) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "category_id": IT_CATEGORY_ID,
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    if query:
        params["query"] = query

    try:
        response = requests.get(
            API_BASE_URL,
            params=params,
            headers=USER_AGENT,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) if isinstance(payload, dict) else []
    except Exception as exc:
        print(f"[Jobs][OLX] API error (offset {offset}): {exc}")
        return []


def fetch_offers(query: Optional[str], max_pages: int) -> List[Dict[str, Any]]:
    offers = []
    for page in range(max_pages):
        page_offers = fetch_offers_page(query, page * PAGE_SIZE)
        if not page_offers:
            break
        offers.extend(page_offers)
    return offers


def collect_offers(filters, max_pages: int) -> List[Dict[str, Any]]:
    if filters.get("offer_status", "active") != "active":
        return []

    location_city = filters.get("location_city")
    include_remote = bool(filters.get("include_remote"))
    user_search = api_filters(filters).get("search")
    collected: List[Dict[str, Any]] = []

    if location_city:
        city_search = merge_search(user_search, location_city)
        city_offers = fetch_offers(city_search, max_pages)
        for offer in city_offers:
            if matches_city({"offer_city": _city_name(offer)}, location_city):
                collected.append(offer)

    if include_remote:
        remote_search = merge_search(user_search, "zdalna")
        remote_offers = fetch_offers(remote_search, max_pages)
        collected.extend(offer for offer in remote_offers if is_fully_remote(offer))

    if not location_city and not include_remote:
        collected.extend(fetch_offers(user_search, max_pages))

    return [normalize_offer(offer) for offer in collected]
