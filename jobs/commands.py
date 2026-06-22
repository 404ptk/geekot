import json
from typing import Optional

import discord
from discord import app_commands

from jobs.config import load_config, save_config
from jobs.constants import DEFAULT_ALLOWED_LEVELS, DEFAULT_CONFIG, GUILD_ID
from jobs.filters import (
    filters_summary,
    levels_summary,
    normalize_allowed_levels,
    update_allowed_levels,
)
from jobs.permissions import has_high_tier_guard
from jobs.state import invalidate_state_for_reseed


def register_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    oferty_group = app_commands.Group(
        name="ofertyfiltry",
        description="Zarządzaj filtrami watchera ofert pracy",
    )

    @oferty_group.command(name="pokaz", description="Pokaż aktualne filtry watchera ofert")
    async def oferty_pokaz(interaction: discord.Interaction):
        if not has_high_tier_guard(interaction.user):
            await interaction.response.send_message(
                "Nie masz wystarczających uprawnień do wykonania tej komendy.",
                ephemeral=True,
            )
            return

        config = load_config()
        filters = config.get("filters", {})
        interval = config.get("interval_minutes", 30)
        channel_id = config.get("discord_channel_id")

        embed = discord.Embed(
            title="Filtry watchera ofert",
            description=filters_summary(filters),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Kanał Discord", value=f"<#{channel_id}>", inline=False)
        embed.add_field(name="Interwał sprawdzania", value=f"co {interval} min", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @oferty_group.command(name="ustaw", description="Ustaw filtry watchera ofert")
    @app_commands.describe(
        miasto="Miasto lokalizacji, np. Rzeszów (puste = bez zmiany)",
        zdalne="Czy uwzględniać w pełni zdalne oferty z dowolnego miasta",
        zrodlo="Źródło ofert (puste = bez zmiany)",
        kategoria="Kategoria IT, np. python, java, php (puste = bez zmiany)",
        szukaj="Dodatkowa fraza wyszukiwania, np. devops (puste = bez zmiany)",
        status="Status ofert",
        wyczysc="Usuń wybrane filtry opcjonalne",
    )
    @app_commands.choices(
        zrodlo=[
            app_commands.Choice(name="Just Join IT", value="justjoin.it"),
            app_commands.Choice(name="No Fluff Jobs", value="nofluffjobs.com"),
            app_commands.Choice(name="Pracuj.pl", value="pracuj.pl"),
        ],
        kategoria=[
            app_commands.Choice(name="Python", value="python"),
            app_commands.Choice(name="Java", value="java"),
            app_commands.Choice(name="PHP", value="php"),
        ],
        status=[
            app_commands.Choice(name="Aktywne", value="active"),
            app_commands.Choice(name="Wygasłe", value="expired"),
        ],
        wyczysc=[
            app_commands.Choice(name="Miasto", value="location_city"),
            app_commands.Choice(name="Zdalne", value="include_remote"),
            app_commands.Choice(name="Poziomy", value="allowed_levels"),
            app_commands.Choice(name="Źródło", value="offer_source"),
            app_commands.Choice(name="Kategoria", value="offer_category"),
            app_commands.Choice(name="Szukaj", value="search"),
            app_commands.Choice(name="Wszystkie opcjonalne", value="all_optional"),
        ],
    )
    async def oferty_ustaw(
        interaction: discord.Interaction,
        miasto: Optional[str] = None,
        zdalne: Optional[bool] = None,
        zrodlo: Optional[app_commands.Choice[str]] = None,
        kategoria: Optional[app_commands.Choice[str]] = None,
        szukaj: Optional[str] = None,
        status: Optional[app_commands.Choice[str]] = None,
        wyczysc: Optional[app_commands.Choice[str]] = None,
    ):
        if not has_high_tier_guard(interaction.user):
            await interaction.response.send_message(
                "Nie masz wystarczających uprawnień do wykonania tej komendy.",
                ephemeral=True,
            )
            return

        config = load_config()
        filters = dict(config.get("filters", DEFAULT_CONFIG["filters"]))

        if wyczysc:
            if wyczysc.value == "all_optional":
                for key in ("location_city", "offer_source", "offer_category", "search"):
                    filters.pop(key, None)
                filters["include_remote"] = False
                filters["allowed_levels"] = list(DEFAULT_ALLOWED_LEVELS)
            elif wyczysc.value == "include_remote":
                filters["include_remote"] = False
            elif wyczysc.value == "allowed_levels":
                filters["allowed_levels"] = list(DEFAULT_ALLOWED_LEVELS)
            else:
                filters.pop(wyczysc.value, None)

        if miasto is not None:
            cleaned_city = miasto.strip()
            if cleaned_city:
                filters["location_city"] = cleaned_city
            else:
                filters.pop("location_city", None)
        if zdalne is not None:
            filters["include_remote"] = zdalne

        if zrodlo:
            filters["offer_source"] = zrodlo.value
        if kategoria:
            filters["offer_category"] = kategoria.value
        if szukaj is not None:
            cleaned = szukaj.strip()
            if cleaned:
                filters["search"] = cleaned
            else:
                filters.pop("search", None)
        if status:
            filters["offer_status"] = status.value

        filters.setdefault("offer_status", "active")
        filters["allowed_levels"] = normalize_allowed_levels(filters.get("allowed_levels"))
        config["filters"] = filters
        save_config(config)
        invalidate_state_for_reseed()

        embed = discord.Embed(
            title="Zaktualizowano filtry ofert",
            description=filters_summary(filters),
            color=discord.Color.green(),
        )
        embed.set_footer(text="Watcher zostanie ponownie zainicjowany i wyśle dopasowane oferty.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @oferty_group.command(name="poziom", description="Ustaw dozwolone poziomy stanowisk")
    @app_commands.describe(
        internship="Internship / staż",
        junior="Junior",
        mid="Mid",
        senior="Senior",
    )
    async def oferty_poziom(
        interaction: discord.Interaction,
        internship: Optional[bool] = None,
        junior: Optional[bool] = None,
        mid: Optional[bool] = None,
        senior: Optional[bool] = None,
    ):
        if not has_high_tier_guard(interaction.user):
            await interaction.response.send_message(
                "Nie masz wystarczających uprawnień do wykonania tej komendy.",
                ephemeral=True,
            )
            return

        config = load_config()
        filters = dict(config.get("filters", DEFAULT_CONFIG["filters"]))

        if all(value is None for value in (internship, junior, mid, senior)):
            embed = discord.Embed(
                title="Poziomy stanowisk",
                description=levels_summary(filters),
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        allowed = update_allowed_levels(
            filters,
            internship=internship,
            junior=junior,
            mid=mid,
            senior=senior,
        )
        if not allowed:
            await interaction.response.send_message(
                "Musisz mieć włączony co najmniej jeden poziom stanowiska.",
                ephemeral=True,
            )
            return

        config["filters"] = filters
        save_config(config)
        invalidate_state_for_reseed()

        embed = discord.Embed(
            title="Zaktualizowano poziomy stanowisk",
            description=levels_summary(filters),
            color=discord.Color.green(),
        )
        embed.set_footer(text="Watcher zostanie ponownie zainicjowany i wyśle dopasowane oferty.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @oferty_group.command(name="reset", description="Przywróć domyślne filtry (Rzeszów + zdalne + bez senior)")
    async def oferty_reset(interaction: discord.Interaction):
        if not has_high_tier_guard(interaction.user):
            await interaction.response.send_message(
                "Nie masz wystarczających uprawnień do wykonania tej komendy.",
                ephemeral=True,
            )
            return

        config = load_config()
        config["filters"] = json.loads(json.dumps(DEFAULT_CONFIG["filters"]))
        save_config(config)
        invalidate_state_for_reseed()

        embed = discord.Embed(
            title="Przywrócono domyślne filtry",
            description=filters_summary(config["filters"]),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    tree.add_command(oferty_group, guild=guild)
