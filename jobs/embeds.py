from typing import Any, Dict

import discord

from jobs.constants import LEVEL_LABELS
from jobs.filters import detect_offer_level
from jobs.providers.isitfair import company_logo_url, source_label


def format_salary(offer: Dict[str, Any]) -> str:
    if offer.get("offer_salary_qualifies") and offer.get("offer_salary_min"):
        interval = offer.get("offer_salary_interval", "monthly")
        suffix = "/mies." if interval == "monthly" else f"/{interval}"
        return (
            f"{offer.get('offer_formatted_salary_min', offer['offer_salary_min'])} – "
            f"{offer.get('offer_formatted_salary_max', offer['offer_salary_max'])} PLN{suffix}"
        )
    return "Brak widełek"


def build_offer_embed(offer: Dict[str, Any]) -> discord.Embed:
    company = offer.get("company") or {}
    company_name = company.get("company_name", "Nieznana firma")
    is_fair = bool(offer.get("offer_is_fair"))

    embed = discord.Embed(
        title=offer.get("offer_title", "Nowa oferta pracy"),
        url=offer.get("offer_href"),
        description=company_name,
        color=discord.Color.green() if is_fair else discord.Color.orange(),
    )

    logo_url = company_logo_url(offer)
    if logo_url:
        embed.set_thumbnail(url=logo_url)

    city = offer.get("offer_city")
    if city:
        embed.add_field(name="Miasto", value=city, inline=True)

    category = offer.get("offer_category")
    if category:
        embed.add_field(name="Kategoria", value=category.upper(), inline=True)

    detected_level = detect_offer_level(offer)
    if detected_level:
        embed.add_field(name="Poziom", value=LEVEL_LABELS.get(detected_level, detected_level), inline=True)

    embed.add_field(name="Wynagrodzenie", value=format_salary(offer), inline=False)

    source = offer.get("offer_source")
    if source:
        embed.add_field(name="Źródło", value=source_label(source), inline=True)

    fair_label = "Tak" if is_fair else "Nie"
    embed.add_field(name="Fair offer", value=fair_label, inline=True)

    published = offer.get("offer_published_at")
    footer = "Is It Fair"
    if published:
        footer += f" • {published}"
    embed.set_footer(text=footer)
    return embed
