from typing import Any, Dict, Optional

SOURCE_LABELS = {
    "justjoin.it": "Just Join IT",
    "nofluffjobs.com": "No Fluff Jobs",
    "pracuj.pl": "Pracuj.pl",
    "olx.pl": "OLX Praca",
}

FOOTER_LABELS = {
    "olx.pl": "OLX Praca",
}


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def footer_label(source: Optional[str]) -> str:
    if source and source in FOOTER_LABELS:
        return FOOTER_LABELS[source]
    return "Is It Fair"


def company_logo_url(offer: Dict[str, Any]) -> Optional[str]:
    source = offer.get("offer_source")
    if source == "olx.pl":
        photos = offer.get("_olx_photos") or []
        if photos:
            photo = photos[0]
            link = photo.get("link") if isinstance(photo, dict) else None
            if isinstance(link, str) and link.startswith("http"):
                return link
        user = offer.get("_olx_user") or {}
        logo = user.get("logo") or user.get("logo_ad_page")
        if isinstance(logo, str) and logo.startswith("http"):
            return logo
        return None

    logo = (offer.get("company") or {}).get("company_logo")
    if not logo:
        return None
    if logo.startswith("http"):
        return logo
    filename = logo.rsplit("/", 1)[-1]
    return f"https://isitfair.pl/storage/logos/{filename}"
