import discord
from discord import app_commands


def register_faceit_command(tree, guild, faceit_nick_autocomplete):
    @tree.command(
        name="faceit",
        description="Pokazuje statystyki gracza Faceit (ELO, LVL, ostatnie mecze)",
        guild=guild,
    )
    @app_commands.describe(nick="Nick gracza Faceit")
    @app_commands.autocomplete(nick=faceit_nick_autocomplete)
    async def faceit(interaction: discord.Interaction, nick: str):
        import faceit_utils as fu

        player_data = fu.get_faceit_player_data(nick)
        if player_data is None:
            await interaction.response.send_message(f"Nie znaleziono gracza o nicku {nick} na Faceit.", ephemeral=True)
            return

        player_id = player_data["player_id"]
        player_nickname = player_data["nickname"]
        matches = fu.get_faceit_player_matches(player_id)
        if matches is None:
            await interaction.response.send_message(
                f"Nie udało się pobrać danych o meczach gracza {player_nickname}.", ephemeral=True
            )
            return

        player_level = player_data.get("games", {}).get("cs2", {}).get("skill_level", "Brak danych")
        player_elo = player_data.get("games", {}).get("cs2", {}).get("faceit_elo", "Brak danych")
        avatar_url = player_data.get("avatar", "https://www.faceit.com/static/img/avatar.png")

        player_level_emoji = str(player_level)
        if str(player_level).isdigit() and interaction.guild:
            emoji_name = f"faceit{player_level}"
            emoji_text = fu.get_guild_emoji_text(interaction.guild, emoji_name)
            player_level_emoji = emoji_text if emoji_text else f":{emoji_name}:"

        faceit_logo = fu.get_guild_emoji_text(interaction.guild, "faceitlogo")
        title_prefix = f"{faceit_logo} " if faceit_logo else ""

        daily_elo_change = ""
        daily_stats = fu.load_daily_stats()
        current_date = fu.datetime.now().strftime("%Y-%m-%d")
        if daily_stats.get("date") == current_date:
            start_elo = daily_stats.get("stats", {}).get(player_nickname)
            if start_elo is not None and isinstance(player_elo, int):
                elo_diff = player_elo - start_elo
                if elo_diff != 0:
                    daily_elo_change = f" ({'+' if elo_diff > 0 else ''}{elo_diff})"

        embed = discord.Embed(
            title=f"{title_prefix} {player_nickname}",
            description=f"{player_level_emoji} | **ELO:** {player_elo}{daily_elo_change}",
            color=discord.Color.orange(),
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(
            name="",
            value=f"[🔗 Profil](https://faceit.com/pl/players/{player_nickname})",
            inline=False,
        )

        total_kills, total_deaths, total_assists, total_hs, total_wins, total_adr = 0, 0, 0, 0, 0, 0
        match_count = len(matches)

        match_summary = "```"
        match_summary += f"{'🗺 Mapa'.ljust(10)} {'📊 Wynik'.ljust(8)} {'🔪 K/D/A'.ljust(8)} {'🎯 HS'.ljust(5)} {'ADR'}\n"
        match_summary += "-" * 40 + "\n"

        for match in matches:
            map_name = match.get("stats", {}).get("Map", "Nieznana").replace("de_", "")
            result = match.get("stats", {}).get("Result", "Brak danych")
            result_display = "✅" if result == "1" else "❌" if result == "0" else "❓"
            kills = int(match.get("stats", {}).get("Kills", 0))
            deaths = int(match.get("stats", {}).get("Deaths", 0))
            assists = int(match.get("stats", {}).get("Assists", 0))
            hs = int(match.get("stats", {}).get("Headshots %", 0))
            adr = float(match.get("stats", {}).get("ADR", 0))

            total_kills += kills
            total_deaths += deaths
            total_assists += assists
            total_hs += hs
            total_adr += adr
            if result == "1":
                total_wins += 1

            match_summary += f"{map_name.ljust(15)} {result_display.ljust(5)} {f'{kills}/{deaths}/{assists}'.ljust(9)} {f'{hs}%'.ljust(5)} {adr:.0f}\n"

        match_summary += "```"
        embed.add_field(name="🎮 Ostatnie 5 meczów", value=match_summary, inline=False)

        avg_kills = int(total_kills / match_count) if match_count else 0
        avg_deaths = int(total_deaths / match_count) if match_count else 0
        avg_hs = total_hs / match_count if match_count else 0
        win_percentage = (total_wins / match_count) * 100 if match_count else 0
        avg_kd = float(avg_kills / avg_deaths) if avg_deaths else 0
        avg_adr = float(total_adr / match_count) if match_count else 0
        embed.add_field(
            name="📊 Średnie statystyki",
            value=f"**K/D:** {avg_kd:.2f} | **HS:** {avg_hs:.0f}% | **ADR:** {avg_adr:.1f}\n**Winrate:** {win_percentage:.0f}%",
            inline=False,
        )

        matches20 = fu.get_faceit_player_matches(player_id, limit=20)
        if matches20:
            total_kills20 = total_deaths20 = total_hs20 = total_wins20 = 0
            total_adr20 = 0.0
            match_count20 = len(matches20)

            for match in matches20:
                result20 = match.get("stats", {}).get("Result", "Brak danych")
                kills20 = int(match.get("stats", {}).get("Kills", 0))
                deaths20 = int(match.get("stats", {}).get("Deaths", 0))
                hs20 = int(match.get("stats", {}).get("Headshots %", 0))
                adr20 = float(match.get("stats", {}).get("ADR", 0))

                total_kills20 += kills20
                total_deaths20 += deaths20
                total_hs20 += hs20
                total_adr20 += adr20
                if result20 == "1":
                    total_wins20 += 1

            avg_kills20 = int(total_kills20 / match_count20) if match_count20 else 0
            avg_deaths20 = int(total_deaths20 / match_count20) if match_count20 else 0
            avg_hs20 = total_hs20 / match_count20 if match_count20 else 0
            avg_kd20 = float(avg_kills20 / avg_deaths20) if avg_deaths20 else 0
            avg_adr20 = float(total_adr20 / match_count20) if match_count20 else 0
            win_percentage20 = (total_wins20 / match_count20) * 100 if match_count20 else 0

            embed.add_field(
                name="📊 Ostatnie 20 gier",
                value=f"**K/D:** {avg_kd20:.2f} | **HS:** {avg_hs20:.0f}% | **ADR:** {avg_adr20:.1f}\n**Winrate:** {win_percentage20:.0f}%",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)
