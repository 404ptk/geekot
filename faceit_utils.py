import requests
import json
import discord
from discord import app_commands
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
player_nicknames = ['utopiasz', 'radzioswir', 'PhesterM9', '-Masny-', '-mateuko', 'Kvzia', 'Kajetov', 'MlodyHubii', 'BEJLI']

FACEIT_RANKING_FILE = "txt/faceit_ranking.txt"

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
            })
    return {
        "map": match_data["rounds"][0]["round_stats"]["Map"],
        "teams": teams
    }

async def get_discordfaceit_stats():
    player_stats = []
    for nickname in player_nicknames:
        player_data = get_faceit_player_data(nickname)
        if player_data:
            player_level = player_data.get('games', {}).get('cs2', {}).get('skill_level', 0)
            player_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', 0)
            player_stats.append({
                'nickname': nickname,
                'level': player_level if isinstance(player_level, int) else 0,
                'elo': player_elo if isinstance(player_elo, int) else 0
            })
    player_stats.sort(key=lambda x: (x['elo'], x['level']), reverse=True)
    previous_stats = load_faceit_ranking()
    previous_positions = {player['nickname']: i for i, player in enumerate(previous_stats)}
    embed = discord.Embed(
        title="📊 **Ranking Faceit**",
        description="🔹 Lista graczy uszeregowana według ELO Faceit.",
        color=discord.Color.orange()
    )
    for index, player in enumerate(player_stats):
        rank_emoji = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else ""
        flag = "🇺🇦" if player['nickname'] == "PhesterM9" else "🇵🇱"
        elo_diff = 0
        position_change = ""
        if player['nickname'] in previous_positions:
            prev_player = next(p for p in previous_stats if p['nickname'] == player['nickname'])
            elo_diff = player['elo'] - prev_player['elo']
            prev_pos = previous_positions[player['nickname']]
            if prev_pos > index:
                position_change = "\t⬆️"
            elif prev_pos < index:
                position_change = "\t⬇️"
            else:
                position_change = "\t➖"
        elo_change_str = f" ({'+' if elo_diff > 0 else ''}{elo_diff})" if elo_diff != 0 else ""
        embed.add_field(
            name=f"{rank_emoji} **{player['nickname']}** {flag} {position_change}",
            value=f"**ELO**: {player['elo']}{elo_change_str} | **LVL**: {player['level']}",
            inline=False
        )
    embed.set_footer(text="📅 Ranking generowany automatycznie | Zmiany względem poprzedniego wywołania")
    save_faceit_ranking(player_stats)
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
    embed = discord.Embed(
        title=f"**Ostatni mecz gracza {player_nickname}**",
        description=f"**Mapa:** {map_name} | {match_result}",
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url=avatar_url)
    match_summary = "```"
    match_summary += f"{'Gracz'.ljust(20)} {'🔪 K/D/A'.ljust(9)} {'🎯 HS'.ljust(6)} {'K/D'.ljust(5)}\n"
    match_summary += "-" * 45 + "\n"
    player_team = None
    for team_name, team_data in match_stats["teams"].items():
        for player in team_data["players"]:
            if player["nickname"] == player_nickname:
                player_team = team_name
                break
        if player_team:
            break
    players_list = []
    for team_name, team_data in match_stats["teams"].items():
        if team_name == player_team:
            for player in team_data["players"]:
                kills = player.get("kills", 0)
                deaths = player.get("deaths", 0)
                assists = player.get("assists", 0)
                hs = player.get("headshots", 0)
                kd_ratio = kills / deaths if deaths > 0 else kills
                players_list.append({
                    "nickname": player["nickname"],
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "hs": hs,
                    "kd_ratio": kd_ratio
                })
    players_list.sort(key=lambda x: x["kills"], reverse=True)
    for player in players_list:
        stats = f"{player['kills']}/{player['deaths']}/{player['assists']}"
        match_summary += f"{player['nickname'].ljust(20)} {stats.ljust(11)} {str(player['hs']).ljust(5)} {player['kd_ratio']:.2f}\n"
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

# ----------------- SLASH COMMANDS -----------------

async def setup_faceit_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    @tree.command(
        name="faceit",
        description="Pokazuje statystyki gracza Faceit (ELO, LVL, ostatnie mecze)",
        guild=guild
    )
    @app_commands.describe(nick="Nick gracza Faceit")
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
    async def last(interaction: discord.Interaction, nick: str):
        embed = await get_last_match_stats(nick)
        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="discordfaceit",
        description="Wyświetla ranking Faceit graczy z discorda",
        guild=guild
    )
    async def discordfaceit(interaction: discord.Interaction):
        embed = await get_discordfaceit_stats()
        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="resetfaceitranking",
        description="Resetuje ranking Faceit (czyści plik rankingowy)",
        guild=guild
    )
    async def resetfaceitranking(interaction: discord.Interaction):
        reset_faceit_ranking()
        await interaction.response.send_message("✅ Ranking Faceit został zresetowany (plik faceit_ranking.txt usunięty).", ephemeral=True)

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