import requests
import json
import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime
import asyncio
import os

GUILD_ID = 551503797067710504

def load_token(filename):
    try:
        with open(filename, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Plik {filename} nie został znaleziony. Upewnij się, że plik istnieje.")
        return None
    except Exception as e:
        print(f"Wystąpił błąd podczas wczytywania tokena z pliku {filename}: {e}")
        return None

FACEIT_API_KEY = load_token('txt/faceit_api.txt')

# Lista pseudonimów graczy do rankingu Discorda
player_nicknames = ['utopiasz', 'radzioswir', 'PhesterM9', '-Masny-', '-mateuko', 'Kvzia', 'Kajetov', 'MlodyHubii']

FACEIT_RANKING_FILE = "txt/faceit_ranking.txt"
FACEIT_DAILY_STATS_FILE = "txt/faceit_daily_stats.json"

def get_faceit_player_data(nickname):
    url = f'https://open.faceit.com/data/v4/players?nickname={nickname}'
    headers = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def get_faceit_player_matches(player_id, limit=5):
    game_id = "cs2"
    url = f'https://open.faceit.com/data/v4/players/{player_id}/games/{game_id}/stats?limit={limit}'
    headers = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('items', [])
    else:
        print("Błąd połączenia z Faceit API:", response.status_code)
        return None

def save_faceit_ranking(player_stats):
    with open(FACEIT_RANKING_FILE, "w") as file:
        json.dump(player_stats, file)

def load_faceit_ranking():
    try:
        with open(FACEIT_RANKING_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_faceit_match_details(match_id):
    url = f"https://open.faceit.com/data/v4/matches/{match_id}/stats"
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    match_data = response.json()
    teams = {}
    for team in match_data["rounds"][0]["teams"]:
        team_name = team["team_id"]
        teams[team_name] = {"players": []}
        for player in team["players"]:
            teams[team_name]["players"].append({
                "nickname": player["nickname"],
                "kills": int(player["player_stats"]["Kills"]),
                "deaths": int(player["player_stats"]["Deaths"]),
                "assists": int(player["player_stats"]["Assists"]),
                "headshots": int(player["player_stats"]["Headshots %"]),
                "adr": player["player_stats"].get("ADR", "0"),
            })
    # Determine final score (e.g., 13:11)
    score = None
    try:
        round_stats = match_data.get("rounds", [{}])[0].get("round_stats", {})
        score_raw = round_stats.get("Score")
        if score_raw:
            score = score_raw.replace(" ", "").replace("/", ":")
        else:
            # Fallback: read from team_stats if available
            teams_list = match_data.get("rounds", [{}])[0].get("teams", [])
            if len(teams_list) == 2:
                t1 = teams_list[0].get("team_stats", {})
                t2 = teams_list[1].get("team_stats", {})
                s1 = t1.get("Final Score") or t1.get("Score") or t1.get("Team Score")
                s2 = t2.get("Final Score") or t2.get("Score") or t2.get("Team Score")
                if s1 and s2:
                    score = f"{s1}:{s2}"
    except Exception:
        pass
    return {
        "map": match_data["rounds"][0]["round_stats"]["Map"],
        "teams": teams,
        "score": score,
    }

async def get_discordfaceit_stats():
    player_stats = []
    # Load daily stats for comparison
    daily_data = load_daily_stats()
    current_date = datetime.now().strftime("%Y-%m-%d")
    is_same_day = daily_data.get("date") == current_date
    daily_start_map = daily_data.get("stats", {}) if is_same_day else {}

    previous_stats = load_faceit_ranking()
    previous_positions = {player['nickname']: i for i, player in enumerate(previous_stats)}
    previous_elo_map = {player['nickname']: player['elo'] for player in previous_stats}

    for nickname in player_nicknames:
        player_data = get_faceit_player_data(nickname)
        if player_data:
            player_level = player_data.get('games', {}).get('cs2', {}).get('skill_level', 0)
            player_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', 0)
            pid = player_data.get('player_id')

            # Fetch last 5 matches
            last_matches_str = "N/A"
            streak_emoji = ""
            if pid:
                matches = get_faceit_player_matches(pid, limit=5)
                if matches:
                    outcomes = []
                    for m in matches:
                        res = m.get('stats', {}).get('Result')
                        if res == '1': outcomes.append('W')
                        elif res == '0': outcomes.append('L')
                        else: outcomes.append('?')
                    last_matches_str = '/'.join(outcomes)
                    
                    if len(outcomes) >= 3:
                        if outcomes[:3] == ['W', 'W', 'W']:
                            streak_emoji = " 🔥"
                        elif outcomes[:3] == ['L', 'L', 'L']:
                            streak_emoji = " 😭"

            # ELO Diff logic
            elo_diff = 0
            if nickname in previous_elo_map:
                elo_diff = player_elo - previous_elo_map[nickname]
            
            elo_change_str = f" ({'+' if elo_diff > 0 else ''}{elo_diff})" if elo_diff != 0 else ""
            elo_full_str = f"ELO: {player_elo}{elo_change_str}"

            player_stats.append({
                'nickname': nickname,
                'level': player_level if isinstance(player_level, int) else 0,
                'elo': player_elo if isinstance(player_elo, int) else 0,
                'elo_full_str': elo_full_str,
                'last_matches': last_matches_str,
                'streak_emoji': streak_emoji
            })

    player_stats.sort(key=lambda x: (x['elo'], x['level']), reverse=True)
    
    # Calculate Max Length for Alignment
    max_elo_len = 0
    for p in player_stats:
        if len(p['elo_full_str']) > max_elo_len:
            max_elo_len = len(p['elo_full_str'])

    embed = discord.Embed(
        title="📊 **Ranking Faceit**",
        description="🔹 Lista graczy uszeregowana według ELO Faceit.",
        color=discord.Color.orange()
    )
    for index, player in enumerate(player_stats):
        rank_emoji = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else ""
        flag = "🇺🇦" if player['nickname'] == "PhesterM9" else "🇵🇱"
        
        position_change = ""
        if player['nickname'] in previous_positions:
            prev_pos = previous_positions[player['nickname']]
            if prev_pos > index:
                position_change = "\t⬆️"
            elif prev_pos < index:
                position_change = "\t⬇️"
            else:
                position_change = "\t➖"
        
        # Obliczanie dobowej różnicy
        daily_diff_str = ""
        if is_same_day:
            start_elo = daily_start_map.get(player['nickname'])
            # Jeśli nie ma start_elo (np. ktoś dodany w trakcie dnia), to pomiń
            if start_elo is not None:
                d_diff = player['elo'] - start_elo
                if d_diff != 0:
                    daily_diff_str = f" \n📅 **Dobowy**: {'+' if d_diff > 0 else ''}{d_diff}"

        padded_elo = player['elo_full_str'].ljust(max_elo_len)
        value_str = f"```\n{padded_elo} | LVL: {player['level']} | {player['last_matches']}{player['streak_emoji']}\n```" + daily_diff_str

        embed.add_field(
            name=f"{rank_emoji} **{player['nickname']}** {flag} {position_change}",
            value=value_str,
            inline=False
        )
    embed.set_footer(text="📅 Ranking generowany automatycznie | Zmiany względem poprzedniego wywołania")
    
    # Save minimal stats for next comparison
    save_list = [{'nickname': p['nickname'], 'level': p['level'], 'elo': p['elo']} for p in player_stats]
    save_faceit_ranking(save_list)
    return embed

async def get_last_match_stats(nickname):
    player_data = get_faceit_player_data(nickname)
    if not player_data:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f'Nie znaleziono gracza o nicku **{nickname}** na Faceit.',
            color=discord.Color.red()
        )
        return embed
    player_id = player_data['player_id']
    player_nickname = player_data['nickname']
    avatar_url = player_data.get('avatar', 'https://www.faceit.com/static/img/avatar.png')
    matches = get_faceit_player_matches(player_id)
    if not matches or len(matches) == 0:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f'Nie udało się pobrać danych o meczach gracza **{player_nickname}**.',
            color=discord.Color.red()
        )
        return embed
    last_match = matches[0]
    match_id = last_match["stats"].get("Match Id")
    if not match_id:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f'Nie udało się znaleźć match_id w danych gracza **{nickname}**.\n🔍 Debug: {last_match}',
            color=discord.Color.red()
        )
        return embed
    result = last_match["stats"].get("Result", "Brak danych")
    match_result = "✅" if result == "1" else "❌" if result == "0" else "❓"
    match_stats = get_faceit_match_details(match_id)
    if not match_stats:
        embed = discord.Embed(
            title="❌ Błąd",
            description=f'Nie udało się pobrać szczegółowych danych o meczu.',
            color=discord.Color.red()
        )
        return embed
    map_name = match_stats.get("map", "Nieznana").replace("de_", "")
    score_display = match_stats.get("score")
    desc = f"**Mapa:** {map_name} | {match_result}"
    if score_display:
        desc += f" | {score_display}"
    embed = discord.Embed(
        title=f"**Ostatni mecz gracza {player_nickname}**",
        description=desc,
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url=avatar_url)
    # Find player's team
    player_team = None
    for team_name, team_data in match_stats["teams"].items():
        for player in team_data["players"]:
            if player["nickname"] == player_nickname:
                player_team = team_name
                break
        if player_team:
            break

    players_list = []
    if player_team:
        for player in match_stats["teams"][player_team]["players"]:
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
            
            players_list.append({
                "nickname": player["nickname"],
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "hs": hs,
                "adr": adr_val,
                "kd_ratio": kd_ratio,
                "kda_str": f"{kills}/{deaths}/{assists}",
                "adr_str": f"{adr_val:.0f}",
                "hs_str": str(hs),
                "kd_str": f"{kd_ratio:.2f}"
            })

    # Sort by ADR (descending)
    players_list.sort(key=lambda x: x["adr"], reverse=True)

    # Calculate dynamic widths
    # Headers: Gracz, K/D/A, K/D, HS, ADR
    # Base widths (min length = header length)
    w_nick = len("Gracz")
    w_kda = len("K/D/A")
    w_kd = len("K/D")
    w_hs = len("HS")
    w_adr = len("ADR")

    for p in players_list:
        w_nick = max(w_nick, len(p["nickname"]))
        w_kda = max(w_kda, len(p["kda_str"]))
        w_kd = max(w_kd, len(p["kd_str"]))
        w_hs = max(w_hs, len(p["hs_str"]))
        w_adr = max(w_adr, len(p["adr_str"]))

    # Add padding (2 spaces)
    pad = 2
    w_nick += pad
    w_kda += pad
    w_kd += pad
    w_hs += pad
    w_adr += pad

    # Construct table
    match_summary = "```\n"
    # Header
    match_summary += f"{'Gracz'.ljust(w_nick)}{'K/D/A'.ljust(w_kda)}{'K/D'.ljust(w_kd)}{'HS'.ljust(w_hs)}{'ADR'.ljust(w_adr)}\n"
    match_summary += "-" * (w_nick + w_kda + w_kd + w_hs + w_adr) + "\n"

    for p in players_list:
        match_summary += (
            f"{p['nickname'].ljust(w_nick)}"
            f"{p['kda_str'].ljust(w_kda)}"
            f"{p['kd_str'].ljust(w_kd)}"
            f"{p['hs_str'].ljust(w_hs)}"
            f"{p['adr_str'].ljust(w_adr)}\n"
        )
    match_summary += "```"
    embed.add_field(
        name=f"📊 Statystyki",
        value=match_summary if match_summary else "Brak danych",
        inline=False
    )
    match_link = f"https://www.faceit.com/en/cs2/room/{match_id}/scoreboard"
    embed.add_field(
        name="",
        value=f"🔗 [Lobby]({match_link})",
        inline=False
    )
    embed.set_footer(text="📊 Statystyki ostatniego meczu | Sprawdź swoje pod /last")
    return embed

def reset_faceit_ranking():
    if os.path.exists(FACEIT_RANKING_FILE):
        os.remove(FACEIT_RANKING_FILE)

def load_daily_stats():
    if os.path.exists(FACEIT_DAILY_STATS_FILE):
        try:
            with open(FACEIT_DAILY_STATS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_daily_stats(data):
    with open(FACEIT_DAILY_STATS_FILE, "w") as f:
        json.dump(data, f)

@tasks.loop(minutes=10)
async def track_daily_elo():
    # Sprawdź czy mamy staty na dziś
    current_date = datetime.now().strftime("%Y-%m-%d")
    data = load_daily_stats()
    
    # Jeśli data w pliku jest inna niż dzisiejsza (czyli minęła północ lub brak pliku)
    if data.get("date") != current_date:
        print(f"[Faceit] Nowy dzień {current_date}. Robię snapshot ELO...")
        new_stats = {}
        for nick in player_nicknames:
            p_data = get_faceit_player_data(nick)
            if p_data:
                elo = p_data.get('games', {}).get('cs2', {}).get('faceit_elo', 0)
                if isinstance(elo, int):
                    new_stats[nick] = elo
        
        data = {
            "date": current_date,
            "stats": new_stats
        }
        save_daily_stats(data)
        print("[Faceit] Zapisano dzienne ELO startowe.")

# ----------------- SLASH COMMANDS -----------------

async def setup_faceit_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    # Autocomplete callback for Faceit nickname
    async def faceit_nick_autocomplete(interaction: discord.Interaction, current: str):
        query = (current or "").lower()
        options = [n for n in player_nicknames if query in n.lower()]
        return [app_commands.Choice(name=n, value=n) for n in options[:25]]

    @tree.command(
        name="faceit",
        description="Pokazuje statystyki gracza Faceit (ELO, LVL, ostatnie mecze)",
        guild=guild
    )
    @app_commands.describe(nick="Nick gracza Faceit")
    @app_commands.autocomplete(nick=faceit_nick_autocomplete)
    async def faceit(interaction: discord.Interaction, nick: str):
        player_data = get_faceit_player_data(nick)
        if player_data is None:
            await interaction.response.send_message(f'Nie znaleziono gracza o nicku {nick} na Faceit.', ephemeral=True)
            return
        player_id = player_data['player_id']
        player_nickname = player_data['nickname']
        matches = get_faceit_player_matches(player_id)  # domyślnie 5
        if matches is None:
            await interaction.response.send_message(f'Nie udało się pobrać danych o meczach gracza {player_nickname}.', ephemeral=True)
            return
        player_level = player_data.get('games', {}).get('cs2', {}).get('skill_level', "Brak danych")
        player_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', 'Brak danych')
        avatar_url = player_data.get('avatar', 'https://www.faceit.com/static/img/avatar.png')
        embed = discord.Embed(
            title=f'{player_nickname}',
            description=f'**LVL:** {player_level} | **ELO:** {player_elo}',
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(
            name="",
            value=f"[🔗 Profil](https://faceit.com/pl/players/{player_nickname})",
            inline=False
        )
        total_kills, total_deaths, total_assists, total_hs, total_wins, total_adr = 0, 0, 0, 0, 0, 0
        match_count = len(matches)
        match_summary = "```"
        match_summary += f"{'🗺 Mapa'.ljust(10)} {'📊 Wynik'.ljust(8)} {'🔪 K/D/A'.ljust(8)} {'🎯 HS'.ljust(5)} {'ADR'}\n"
        match_summary += "-" * 40 + "\n"
        for match in matches:
            map_name = match.get('stats', {}).get('Map', 'Nieznana').replace('de_', '')
            result = match.get('stats', {}).get('Result', 'Brak danych')
            result_display = '✅' if result == '1' else '❌' if result == '0' else '❓'
            kills = int(match.get('stats', {}).get('Kills', 0))
            deaths = int(match.get('stats', {}).get('Deaths', 0))
            assists = int(match.get('stats', {}).get('Assists', 0))
            hs = int(match.get('stats', {}).get('Headshots %', 0))
            adr = float(match.get('stats', {}).get('ADR', 0))
            total_kills += kills
            total_deaths += deaths
            total_assists += assists
            total_hs += hs
            total_adr += adr
            if result == '1':
                total_wins += 1
            match_summary += f"{map_name.ljust(15)} {result_display.ljust(5)} {f'{kills}/{deaths}/{assists}'.ljust(9)} {f'{hs}%'.ljust(5)} {adr:.0f}\n"
        match_summary += "```"
        embed.add_field(name="🎮 Ostatnie 5 meczów", value=match_summary, inline=False)
        avg_kills = int(total_kills / match_count) if match_count else 0
        avg_deaths = int(total_deaths / match_count) if match_count else 0
        avg_assists = int(total_assists / match_count) if match_count else 0
        avg_hs = total_hs / match_count if match_count else 0
        win_percentage = (total_wins / match_count) * 100 if match_count else 0
        avg_kd = float(avg_kills / avg_deaths) if avg_deaths else 0
        avg_adr = float(total_adr / match_count) if match_count else 0
        embed.add_field(
            name="📊 Średnie statystyki",
            value=f"**K/D:** {avg_kd:.2f} | **HS:** {avg_hs:.0f}% | **ADR:** {avg_adr:.1f}\n**Winrate:** {win_percentage:.0f}%",
            inline=False
        )
        # Dodatkowe średnie z ostatnich 20 meczów
        matches20 = get_faceit_player_matches(player_id, limit=20)
        if matches20:
            total_kills20 = total_deaths20 = total_assists20 = total_hs20 = total_wins20 = 0
            total_adr20 = 0.0
            match_count20 = len(matches20)
            for match in matches20:
                result20 = match.get('stats', {}).get('Result', 'Brak danych')
                kills20 = int(match.get('stats', {}).get('Kills', 0))
                deaths20 = int(match.get('stats', {}).get('Deaths', 0))
                assists20 = int(match.get('stats', {}).get('Assists', 0))
                hs20 = int(match.get('stats', {}).get('Headshots %', 0))
                adr20 = float(match.get('stats', {}).get('ADR', 0))
                total_kills20 += kills20
                total_deaths20 += deaths20
                total_assists20 += assists20
                total_hs20 += hs20
                total_adr20 += adr20
                if result20 == '1':
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
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="last",
        description="Pokazuje szczegóły ostatniego meczu gracza Faceit",
        guild=guild
    )
    @app_commands.describe(nick="Nick gracza Faceit")
    @app_commands.autocomplete(nick=faceit_nick_autocomplete)
    async def last(interaction: discord.Interaction, nick: str):
        embed = await get_last_match_stats(nick)
        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="discordfaceit",
        description="Wyświetla ranking Faceit graczy z discorda",
        guild=guild
    )
    async def discordfaceit(interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await get_discordfaceit_stats()
        await interaction.followup.send(embed=embed)

    @tree.command(
        name="resetfaceitranking",
        description="Resetuje ranking Faceit (czyści plik rankingowy)",
        guild=guild
    )
    async def resetfaceitranking(interaction: discord.Interaction):
        reset_faceit_ranking()
        await interaction.response.send_message("✅ Ranking Faceit został zresetowany (plik faceit_ranking.txt usunięty).", ephemeral=True)

    if not track_daily_elo.is_running():
        track_daily_elo.start()

MASNY_FILE = "txt/masny.txt"

# Zdjęcia dla miejsc 1-5
image_links = {
    "1": "https://cdn.discordapp.com/attachments/809156611167748176/1330901097816129596/BE8227A4-FD7F-42E4-A48F-350CD124D92B.png?ex=678fa9bc&is=678e583c&hm=ac937a4d34a9375cc56fefdbb1d228733a3fdf0daaaa720e5a020ecd302a878e&",
    "2": "https://cdn.discordapp.com/attachments/809156611167748176/1330905145772474428/61A0B076-BD51-400C-AF19-A7B1D626B1B1.png?ex=678fad81&is=678e5c01&hm=6f06532e17ca3e49d550adc2cf84ff19f80b91e5b7b8833c7c7dc54061f40882&",
    "3": "https://cdn.discordapp.com/attachments/809156611167748176/1330911802049036340/2698389E-237A-4840-8A63-07F996640858.png?ex=678fb3b4&is=678e6234&hm=4870f7636f0053600f02e59e2c9332c5c0272d04e8cb25d25ad643c6f2947739&",
    "4": "https://media.discordapp.net/attachments/778302928338550865/1300471813146415176/B4B5C4D4-8E00-43CE-927B-E9CC47FB2201.png?ex=678fb441&is=678e62c1&hm=661a9436fdf6bbe526df0afa62a28adf1ae8a4dbca4dab0f333d4a4c059d9a0d&=&format=webp&quality=lossless&width=359&height=601",
    "5": "https://cdn.discordapp.com/attachments/809156611167748176/1330906894302318592/pobrane_1.gif?ex=678faf22&is=678e5da2&hm=908f4934957c128b1531edc28da1820b096fd8a1bd35358621e794336969884e&"
}

def load_masny_data():
    # Zwraca słownik {"1": 0, "2": 0, ...}
    if os.path.exists(MASNY_FILE):
        try:
            with open(MASNY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for i in range(1, 6):
                    data.setdefault(str(i), 0)
                return data
        except Exception:
            pass
    return {str(i): 0 for i in range(1, 6)}

def save_masny_data(data):
    with open(MASNY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

async def setup_masny_command(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    @tree.command(
        name="masny",
        description="Dodaj, odejmij lub pokaż statystyki miejsc Masnego (1-5, -1 do odjęcia)",
        guild=guild
    )
    @app_commands.describe(
        miejsce="Miejsce od 1 do 5 (np. 1, 2, ...), lub -1 do -5 do odejmowania. Puste = statystyki."
    )
    async def masny(interaction: discord.Interaction, miejsce: str = None):
        masny_counter = load_masny_data()

        if miejsce is None:
            # Wyświetl statystyki
            total_counts = sum(masny_counter.values())
            if total_counts == 0:
                await interaction.response.send_message("Brak danych o miejscach Masnego.")
                return

            weighted_sum = sum(int(key) * count for key, count in masny_counter.items())
            avg_position = weighted_sum / total_counts if total_counts > 0 else 0
            most_common_position = max(masny_counter, key=masny_counter.get) if total_counts > 0 else None

            embed = discord.Embed(
                title="📊 Miejsca w tabeli Masnego",
                color=discord.Color.blue()
            )

            for key in sorted(masny_counter.keys()):
                count = masny_counter[key]
                percent = (count / total_counts) * 100 if total_counts > 0 else 0
                embed.add_field(name=f"🏅 **{key} miejsce**", value=f"{count} razy *({percent:.2f}%)*", inline=False)

            embed.add_field(name="\u200b", value="", inline=False)
            embed.add_field(name="📉 Średnie miejsce", value=f"**{avg_position:.2f}**", inline=False)
            embed.add_field(name="📌 Masny najczęściej zajmuje", value=f"**{most_common_position}** miejsce", inline=False)
            embed.add_field(name="\u200b", value="", inline=False)
            embed.set_footer(text="Aby dopisać miejsce Masnego w tabeli wpisz `/masny [miejsce]`")

            await interaction.response.send_message(embed=embed)
            return

        miejsce = miejsce.strip()
        # Odejmowanie miejsca
        if miejsce.startswith('-') and miejsce[1:] in masny_counter:
            place = miejsce[1:]
            if masny_counter[place] > 0:
                masny_counter[place] -= 1
                save_masny_data(masny_counter)
                embed = discord.Embed(
                    title="📉 Aktualizacja tabeli Masnego",
                    description=f"Miejsce **{place}** zostało zmniejszone o 1.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Błąd",
                    description=f"Miejsce **{place}** jest już na zerze i nie można go dalej zmniejszać.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
            return

        # Dodawanie miejsca
        if miejsce in masny_counter:
            masny_counter[miejsce] += 1
            save_masny_data(masny_counter)
            embed = discord.Embed(
                title=f"🏆 Masny zajął {miejsce} miejsce!",
                color=discord.Color.gold()
            )
            image_url = image_links.get(miejsce)
            if image_url:
                embed.set_image(url=image_url)
            embed.add_field(name="📊 Statystyki", value=f"Zaktualizowano miejsce **{miejsce}**.", inline=False)
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.send_message(
            "Niepoprawny format miejsca. Użyj liczby od 1 do 5 lub -[1-5] do odejmowania.", ephemeral=True
        )

    print("Slash command /masny zarejestrowany w faceit_utils.py")