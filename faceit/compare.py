import discord
from discord import app_commands

from faceit.common import get_faceit_level_badge, get_guild_emoji_text


EMBED_LINE_WIDTH = 40


def _format_value(value, suffix=""):
    try:
        if isinstance(value, float):
            return f"{value:.2f}{suffix}"
        if isinstance(value, int):
            return f"{value}{suffix}"
        number = float(value)
        return f"{number:.2f}{suffix}"
    except Exception:
        return f"{value}{suffix}"


def _center_line(text: str) -> str:
    if len(text) >= EMBED_LINE_WIDTH:
        return text
    left = (EMBED_LINE_WIDTH - len(text)) // 2
    right = EMBED_LINE_WIDTH - len(text) - left
    return f"{' ' * left}{text}{' ' * right}"


def _code_line(text: str) -> str:
    return f"`{_center_line(text)}`"


def register_compare_command(tree, guild, faceit_nick_autocomplete):
    @tree.command(
        name="compare",
        description="Porównuje statystyki dwóch graczy Faceit (ostatnie 10 meczów)",
        guild=guild,
    )
    @app_commands.describe(nick1="Pierwszy nick", nick2="Drugi nick")
    @app_commands.autocomplete(nick1=faceit_nick_autocomplete, nick2=faceit_nick_autocomplete)
    async def compare(interaction: discord.Interaction, nick1: str, nick2: str):
        await interaction.response.defer()

        import faceit_utils as fu

        def gather_player_summary(player_data):
            pid = player_data.get("player_id")
            nick = player_data.get("nickname")
            avatar = player_data.get("avatar", "https://www.faceit.com/static/img/avatar.png")
            matches = fu.get_faceit_player_matches(pid, limit=10) or []

            outcomes = []
            total_kills = total_deaths = total_assists = total_hs = total_adr = 0
            total_wins = 0
            total_clutch_wins = total_clutch_count = 0
            total_flash_success = total_flash_count = 0
            total_entry_wins = total_entry_count = 0
            total_utility = 0
            total_mvps = 0

            for match in matches:
                stats = match.get("stats", {})
                result = stats.get("Result")
                outcomes.append("W" if result == "1" else "L" if result == "0" else "?")

                kills = int(stats.get("Kills", 0))
                deaths = int(stats.get("Deaths", 0))
                assists = int(stats.get("Assists", 0))
                hs = int(stats.get("Headshots %", 0))
                try:
                    adr = float(stats.get("ADR", 0))
                except Exception:
                    adr = 0.0

                total_kills += kills
                total_deaths += deaths
                total_assists += assists
                total_hs += hs
                total_adr += adr
                if result == "1":
                    total_wins += 1

                match_id = stats.get("Match Id")
                if not match_id:
                    continue

                details = fu.get_faceit_match_details(match_id)
                if not details:
                    continue

                for team in details.get("teams", {}).values():
                    for player in team.get("players", []):
                        if player.get("nickname") != nick:
                            continue

                        clutch = player.get("clutch", {"count": 0, "wins": 0})
                        flash = player.get("flash", {"count": 0, "successes": 0})
                        entry = player.get("entry", {"count": 0, "wins": 0})
                        utility = player.get("utility_dmg", 0)
                        mvps = player.get("mvps", 0)

                        total_clutch_count += clutch.get("count", 0)
                        total_clutch_wins += clutch.get("wins", 0)
                        total_flash_count += flash.get("count", 0)
                        total_flash_success += flash.get("successes", 0)
                        total_entry_count += entry.get("count", 0)
                        total_entry_wins += entry.get("wins", 0)
                        try:
                            total_utility += int(utility)
                        except Exception:
                            try:
                                total_utility += int(float(utility))
                            except Exception:
                                pass
                        total_mvps += int(mvps or 0)
                        break
                    else:
                        continue
                    break

            match_count = len(matches) if matches else 0
            avg_kd = (total_kills / match_count) / (total_deaths / match_count) if total_deaths > 0 and match_count else float(total_kills / match_count) if match_count else 0.0
            avg_adr = (total_adr / match_count) if match_count else 0.0
            winrate = (total_wins / match_count * 100) if match_count else 0
            avg_utility = (total_utility / match_count) if match_count else 0
            flash_pct = (total_flash_success / total_flash_count * 100) if total_flash_count else 0
            entry_pct = (total_entry_wins / total_entry_count * 100) if total_entry_count else 0
            clutch_pct = (total_clutch_wins / total_clutch_count * 100) if total_clutch_count else 0

            return {
                "nick": nick,
                "player_id": pid,
                "avatar": avatar,
                "matches": matches,
                "outcomes": outcomes,
                "match_count": match_count,
                "avg_kd": avg_kd,
                "avg_adr": avg_adr,
                "winrate": winrate,
                "avg_utility": avg_utility,
                "flash_pct": flash_pct,
                "entry_pct": entry_pct,
                "clutch_pct": clutch_pct,
                "total_mvps": total_mvps,
                "elo": player_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0),
                "level": player_data.get("games", {}).get("cs2", {}).get("skill_level", 0),
            }

        p1_data = fu.get_faceit_player_data(nick1)
        p2_data = fu.get_faceit_player_data(nick2)

        if not p1_data or not p2_data:
            missing = nick1 if not p1_data else nick2
            await interaction.followup.send(f"Nie znaleziono gracza: {missing}", ephemeral=True)
            return

        s1 = gather_player_summary(p1_data)
        s2 = gather_player_summary(p2_data)

        faceit_logo = get_guild_emoji_text(interaction.guild, "faceitlogo")
        title_prefix = f"{faceit_logo} " if faceit_logo else ""

        daily_stats = fu.load_daily_stats()
        current_date = fu.datetime.now().strftime("%Y-%m-%d")

        def daily_change(nick, elo):
            if daily_stats.get("date") != current_date:
                return ""
            start = daily_stats.get("stats", {}).get(nick)
            if start is not None and isinstance(elo, int):
                diff = elo - start
                return f" ({'+' if diff > 0 else ''}{diff})" if diff != 0 else ""
            return ""

        p1_daily = daily_change(s1["nick"], s1["elo"])
        p2_daily = daily_change(s2["nick"], s2["elo"])

        embed = discord.Embed(
            title=f"{title_prefix}Porównanie: {s1['nick']}  —  {s2['nick']}",
            description=(
                f"{get_faceit_level_badge(interaction.guild, s1['level'])} {s1['nick']} | **ELO:** {s1['elo']}{p1_daily}\n"
                f"vs\n"
                f"{get_faceit_level_badge(interaction.guild, s2['level'])} {s2['nick']} | **ELO:** {s2['elo']}{p2_daily}"
            ),
            color=discord.Color.orange(),
        )
        embed.set_thumbnail(url=s1.get("avatar"))

        def stat_field(label, left_value, right_value, suffix=""):
            combined = f"{_format_value(left_value, suffix)}   {_format_value(right_value, suffix)}"
            return _code_line(label) + "\n" + _code_line(combined)

        embed.add_field(name="📊 Statystyki", value=stat_field("K/D", s1["avg_kd"], s2["avg_kd"]), inline=False)
        embed.add_field(name="", value=stat_field("ADR", s1["avg_adr"], s2["avg_adr"]), inline=False)
        embed.add_field(name="", value=stat_field("Winrate %", s1["winrate"], s2["winrate"]), inline=False)
        embed.add_field(name="", value=stat_field("Utility (avg dmg)", s1["avg_utility"], s2["avg_utility"]), inline=False)
        embed.add_field(name="", value=stat_field("Flash success %", s1["flash_pct"], s2["flash_pct"]), inline=False)
        embed.add_field(name="", value=stat_field("Entry success %", s1["entry_pct"], s2["entry_pct"]), inline=False)
        embed.add_field(name="", value=stat_field("Clutch success %", s1["clutch_pct"], s2["clutch_pct"]), inline=False)
        embed.add_field(name="", value=stat_field("MVPs (total)", s1["total_mvps"], s2["total_mvps"]), inline=False)

        embed.set_footer(text="Porównanie na podstawie ostatnich 10 gier")
        await interaction.followup.send(embed=embed)
