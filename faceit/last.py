import discord
from discord import app_commands
import requests
from faceit.common import get_faceit_level_badge, get_guild_emoji_text


async def get_last_match_stats(nickname, guild=None):
    import faceit_utils as fu

    player_data = fu.get_faceit_player_data(nickname)
    if not player_data:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f"Nie znaleziono gracza o nicku **{nickname}** na Faceit.",
            color=discord.Color.red(),
        )
        return embed

    player_id = player_data["player_id"]
    player_nickname = player_data["nickname"]
    avatar_url = player_data.get("avatar", "https://www.faceit.com/static/img/avatar.png")
    player_elo = player_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0)

    matches = fu.get_faceit_player_matches(player_id)
    if not matches or len(matches) == 0:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f"Nie udało się pobrać danych o meczach gracza **{player_nickname}**.",
            color=discord.Color.red(),
        )
        return embed

    last_match = matches[0]
    match_id = last_match["stats"].get("Match Id")
    if not match_id:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f"Nie udało się znaleźć match_id w danych gracza **{nickname}**.\n🔍 Debug: {last_match}",
            color=discord.Color.red(),
        )
        return embed

    result = last_match["stats"].get("Result", "Brak danych")
    match_result = "✅" if result == "1" else "❌" if result == "0" else "❓"
    match_stats = fu.get_faceit_match_details(match_id)
    if not match_stats:
        embed = discord.Embed(
            title="❌ Błąd",
            description="Nie udało się pobrać szczegółowych danych o meczu.",
            color=discord.Color.red(),
        )
        return embed

    url = f"https://open.faceit.com/data/v4/matches/{match_id}"
    response = requests.get(url, headers={"Authorization": f"Bearer {fu.FACEIT_API_KEY}"})
    ratings = {}
    if response.status_code == 200:
        match_general = response.json()
        for faction in ["faction1", "faction2"]:
            f_data = match_general.get("teams", {}).get(faction, {})
            f_id = f_data.get("faction_id")
            f_name = f_data.get("name")
            f_rating = f_data.get("stats", {}).get("rating", 0)
            if f_id:
                ratings[f_id] = {"name": f_name, "rating": f_rating}

    player_team = None
    for team_name, team_data in match_stats["teams"].items():
        for player in team_data["players"]:
            if player["nickname"] == player_nickname:
                player_team = team_name
                break
        if player_team:
            break

    enemy_team = None
    for tid in match_stats["teams"]:
        if tid != player_team:
            enemy_team = tid

    team_rating_str = ""
    if ratings and player_team and enemy_team:
        p_team = ratings.get(player_team, {})
        e_team = ratings.get(enemy_team, {})
        p_rating = p_team.get("rating", 0)
        e_rating = e_team.get("rating", 0)

        diff = p_rating - e_rating
        diff_str = f"+{diff}" if diff > 0 else str(diff)

        team_rating_str = f"MMR: {p_rating} VS {e_rating} | ({diff_str})\n"

        player_diff = player_elo - p_rating

        if player_diff < 0:
            abs_diff = abs(player_diff)
            if abs_diff < 100:
                team_rating_str += f"⬆️ {player_nickname} zagrał na MMR wyższym o **{abs_diff} elo**\n"
            else:
                team_rating_str += f"⬆️ {player_nickname} zagrał na MMR wyższym **aż o {abs_diff} elo**\n"
        elif player_diff > 0:
            if player_diff < 100:
                team_rating_str += f"⬇️ {player_nickname} zagrał na MMR niższym o **{player_diff} elo**\n"
            else:
                team_rating_str += f"⬇️ {player_nickname} zagrał na MMR niższym **aż o {player_diff} elo**\n"
        else:
            team_rating_str += f"➡️ {player_nickname} zagrał na średnim MMR drużyny\n"

    map_name = match_stats.get("map", "Nieznana").replace("de_", "")
    last_stats = last_match.get("stats", {})

    def format_halftime_score(first_half_raw):
        if first_half_raw is None:
            return None
        raw = str(first_half_raw).strip()
        if not raw:
            return None
        try:
            player_first_half = int(raw)
            return f"{player_first_half}:{12 - player_first_half}"
        except ValueError:
            return None

    def format_final_score_player_first(stats):
        score_raw = stats.get("Score")
        if not score_raw:
            return match_stats.get("score")

        normalized = str(score_raw).strip().replace(":", "/")
        parts = [part.strip() for part in normalized.split("/") if part.strip()]
        if len(parts) != 2:
            return normalized.replace(" ", "").replace("/", ":")

        try:
            team_a, team_b = int(parts[0]), int(parts[1])
        except ValueError:
            return normalized.replace(" ", "").replace("/", ":")

        final_score_raw = stats.get("Final Score")
        if final_score_raw is not None and str(final_score_raw).strip():
            try:
                player_rounds = int(str(final_score_raw).strip())
                enemy_rounds = team_b if team_a == player_rounds else team_a
                return f"{player_rounds}:{enemy_rounds}"
            except ValueError:
                pass

        result = stats.get("Result")
        if result == "1":
            return f"{max(team_a, team_b)}:{min(team_a, team_b)}"
        if result == "0":
            return f"{min(team_a, team_b)}:{max(team_a, team_b)}"
        return f"{team_a}:{team_b}"

    first_half_display = format_halftime_score(last_stats.get("First Half Score"))
    score_display = format_final_score_player_first(last_stats)

    desc = f"**Mapa:** {map_name} | {match_result}"
    if score_display:
        if first_half_display:
            desc += f" | {first_half_display} -> {score_display}\n"
        else:
            desc += f" | {score_display}\n"
    if team_rating_str:
        desc += f"\n{team_rating_str}"

    faceit_logo = get_guild_emoji_text(guild, "faceitlogo")
    title_prefix = f"{faceit_logo} " if faceit_logo else ""

    embed = discord.Embed(
        title=f"{title_prefix} **Ostatni mecz gracza {player_nickname}**",
        description=desc,
        color=discord.Color.orange(),
    )
    embed.set_thumbnail(url=avatar_url)

    roster = fu.get_faceit_match_roster(match_id)

    p_name = "Twoja drużyna"
    e_name = "Przeciwnik"
    if ratings and player_team and enemy_team:
        p_team = ratings.get(player_team, {})
        e_team = ratings.get(enemy_team, {})
        p_name = p_team.get("name", "Twoja drużyna")
        e_name = e_team.get("name", "Przeciwnik")

    def parse_team_players(team_key):
        players = []
        team_player_detailed_stats = None

        for player in match_stats["teams"][team_key]["players"]:
            if player["nickname"] == player_nickname:
                team_player_detailed_stats = player

            kills = player.get("kills", 0)
            deaths = player.get("deaths", 0)
            assists = player.get("assists", 0)
            hs = player.get("headshots", 0)
            adr = player.get("adr", "0")
            try:
                adr_val = float(adr)
            except ValueError:
                adr_val = 0.0

            kd_ratio = kills / deaths if deaths > 0 else float(kills)

            p_level = roster.get(player["nickname"], {}).get("level", 0)
            level_badge = get_faceit_level_badge(guild, p_level)

            players.append(
                {
                    "nickname": player["nickname"],
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "hs": hs,
                    "adr": adr_val,
                    "adr_str": f"{adr_val:.0f}",
                    "hs_str": str(hs),
                    "kd_str": f"{kd_ratio:.2f}",
                    "level_badge": level_badge,
                    "is_target": player["nickname"] == player_nickname,
                    "is_premade": player["nickname"] in fu.player_nicknames,
                }
            )

        players.sort(key=lambda x: x["adr"], reverse=True)
        return players, team_player_detailed_stats

    player_team_players = []
    player_detailed_stats = None
    if player_team:
        player_team_players, player_detailed_stats = parse_team_players(player_team)

    enemy_team_players = []
    if enemy_team:
        enemy_team_players, _ = parse_team_players(enemy_team)

    all_players = player_team_players + enemy_team_players
    w_nick = len("Nick")
    w_k = len("K")
    w_d = len("D")
    w_a = len("A")
    w_kd = len("K/D")
    w_hs = len("HS")
    w_adr = len("ADR")

    for p in all_players:
        w_nick = max(w_nick, len(p["nickname"]))
        w_k = max(w_k, len(str(p["kills"])))
        w_d = max(w_d, len(str(p["deaths"])))
        w_a = max(w_a, len(str(p["assists"])))
        w_kd = max(w_kd, len(p["kd_str"]))
        w_hs = max(w_hs, len(p["hs_str"]))
        w_adr = max(w_adr, len(p["adr_str"]))

    pad = 1
    w_nick += pad
    w_k += pad
    w_d += pad
    w_a += pad
    w_kd += pad
    w_hs += pad
    w_adr += pad

    def format_team_stats(players):
        header = (
            f"`-- {'Nick'.ljust(w_nick)}{'K'.ljust(w_k)}{'D'.ljust(w_d)}{'A'.ljust(w_a)}"
            f"{'K/D'.ljust(w_kd)}{'ADR'.ljust(w_adr)}{'HS'.ljust(w_hs)}`\n"
        )
        team_table = header

        for p in players:
            line = f"{p['level_badge']} `{p['nickname'].ljust(w_nick)}"
            line += f"{str(p['kills']).ljust(w_k)}"
            line += f"{str(p['deaths']).ljust(w_d)}"
            line += f"{str(p['assists']).ljust(w_a)}"
            line += f"{p['kd_str'].ljust(w_kd)}"
            line += f"{p['adr_str'].ljust(w_adr)}"
            line += f"{p['hs_str'].ljust(w_hs)}`"
            if p["is_target"]:
                line += " 🎯"
            elif p["is_premade"]:
                line += " 🤝"
            line += "\n"
            team_table += line

        return team_table

    player_team_stats = format_team_stats(player_team_players)
    embed.add_field(
        name=f"🛡️ {p_name}",
        value=player_team_stats if player_team_stats else "Brak danych",
        inline=False,
    )

    if enemy_team_players:
        enemy_team_stats = format_team_stats(enemy_team_players)
        embed.add_field(
            name=f"🛡️ {e_name}",
            value=enemy_team_stats if enemy_team_stats else "Brak danych",
            inline=False,
        )

    if player_detailed_stats:
        pds = player_detailed_stats
        mk = pds.get("multikills", {"2k": 0, "3k": 0, "4k": 0, "5k": 0})
        entry = pds.get("entry", {"count": 0, "wins": 0})
        clutch = pds.get("clutch", {"count": 0, "wins": 0})
        flash = pds.get("flash", {"count": 0, "successes": 0})
        udmg = pds.get("utility_dmg", 0)
        kr = pds.get("kr_ratio", "0")
        mvps = pds.get("mvps", 0)

        mk_parts = []
        if mk.get("2k", 0) > 0:
            mk_parts.append(f"2x: `{mk['2k']}`")
        if mk.get("3k", 0) > 0:
            mk_parts.append(f"3x: `{mk['3k']}`")
        if mk.get("4k", 0) > 0:
            mk_parts.append(f"4x: `{mk['4k']}`")
        if mk.get("5k", 0) > 0:
            mk_parts.append(f"5x: `{mk['5k']}`")

        mk_str = f"**Kills:** {' | '.join(mk_parts)}\n" if mk_parts else ""

        adv_stats = (
            f"{mk_str}"
            f"**Entry:** `{entry['wins']}/{entry['count']}`\n"
            f"**Clutche:** `{clutch['wins']}/{clutch['count']}`\n"
            f"**Flashe:** `{flash['successes']}/{flash['count']}`\n"
            f"**Utility Dmg:** `{udmg}`\n"
            f"**K/R Ratio:** `{kr}`\n"
            f"**MVP:** `{mvps}`"
        )
        embed.add_field(
            name=f"Statystyki gracza {player_nickname}",
            value=adv_stats,
            inline=False,
        )

    match_link = f"https://www.faceit.com/en/cs2/room/{match_id}/scoreboard"
    embed.add_field(name="", value=f"🔗 [Lobby]({match_link})", inline=False)
    embed.set_footer(text="📊 Statystyki ostatniego meczu | Sprawdź swoje pod /last")
    return embed


def register_last_command(tree, guild, faceit_nick_autocomplete):
    @tree.command(
        name="last",
        description="Pokazuje szczegóły ostatniego meczu gracza Faceit",
        guild=guild,
    )
    @app_commands.describe(nick="Nick gracza Faceit")
    @app_commands.autocomplete(nick=faceit_nick_autocomplete)
    async def last(interaction: discord.Interaction, nick: str):
        await interaction.response.defer()
        embed = await get_last_match_stats(nick, interaction.guild)
        await interaction.followup.send(embed=embed)
