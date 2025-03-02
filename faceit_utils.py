import requests
import json
import discord

#TODO:
# komenda na reset

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

# Lista pseudonimów graczy
player_nicknames = ['utopiasz', 'radzioswir', 'PhesterM9', '-Masny-',
                    '-mateuko', 'Kvzia', 'Kajetov', 'MlodyHubii']


# Funkcja do pobierania danych o użytkowniku z Faceit
def get_faceit_player_data(nickname):
    url = f'https://open.faceit.com/data/v4/players?nickname={nickname}'
    headers = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None


# Funkcja do pobierania ostatnich meczów gracza
def get_faceit_player_matches(player_id):
    game_id = "cs2"
    url = f'https://open.faceit.com/data/v4/players/{player_id}/games/{game_id}/stats?limit=5'
    headers = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        # Wyświetlenie pełnej odpowiedzi JSON dla analizy
        # print("Faceit API:", response.json())
        return response.json().get('items', [])  # Zwraca pustą listę jeśli nie ma 'items'
    else:
        print("Błąd połączenia z Faceit API:", response.status_code)
        return None


# Plik do przechowywania poprzednich danych rankingu
FACEIT_RANKING_FILE = "txt/faceit_ranking.txt"


# Funkcja do zapisywania danych rankingu do pliku
def save_faceit_ranking(player_stats):
    with open(FACEIT_RANKING_FILE, "w") as file:
        json.dump(player_stats, file)


# Funkcja do wczytywania poprzednich danych rankingu
def load_faceit_ranking():
    try:
        with open(FACEIT_RANKING_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Funkcja do pobierania statystyk dla graczy w Discordzie
async def get_discordfaceit_stats():
    player_stats = []

    # Pobieranie nowych danych z Faceit
    for nickname in player_nicknames:
        player_data = get_faceit_player_data(nickname)
        if player_data:
            player_level = player_data.get('games', {}).get('cs2', {}).get('skill_level', "Brak danych")
            player_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', "Brak danych")
            player_stats.append({
                'nickname': nickname,
                'level': player_level if isinstance(player_level, int) else 0,
                'elo': player_elo if isinstance(player_elo, int) else 0
            })

    # Sortowanie według ELO i poziomu
    player_stats.sort(key=lambda x: (x['elo'], x['level']), reverse=True)

    # Wczytanie poprzednich danych
    previous_stats = load_faceit_ranking()
    previous_positions = {player['nickname']: i for i, player in enumerate(previous_stats)}

    # Tworzenie embeda
    embed = discord.Embed(
        title="📊 **Ranking Faceit**",
        description="🔹 Lista graczy uszeregowana według ELO i poziomu CS2.",
        color=discord.Color.blue()
    )

    # Dodanie graczy do embeda z porównaniem
    for index, player in enumerate(player_stats):
        rank_emoji = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else "🎮"
        flag = "🇺🇦" if player['nickname'] == "PhesterM9" else "🇵🇱"

        # Porównanie ELO i pozycji
        elo_diff = 0
        position_change = ""
        if player['nickname'] in previous_positions:
            prev_player = next(p for p in previous_stats if p['nickname'] == player['nickname'])
            elo_diff = player['elo'] - prev_player['elo']
            prev_pos = previous_positions[player['nickname']]
            if prev_pos > index:
                position_change = "\t⬆️"  # Awans
            elif prev_pos < index:
                position_change = "\t⬇️"  # Spadek
            else:
                position_change = "\t➖"  # Bez zmian

        elo_change_str = f" ({'+' if elo_diff > 0 else ''}{elo_diff})" if elo_diff != 0 else ""
        embed.add_field(
            name=f"{rank_emoji} **{player['nickname']}** {flag} {position_change}",
            value=f"**ELO**: {player['elo']}{elo_change_str} | **LVL**: {player['level']}",
            inline=False
        )

    # Stopka i dodatkowe info
    embed.set_footer(text="📅 Ranking generowany automatycznie | Zmiany względem poprzedniego wywołania")

    # Zapis nowych danych do pliku
    save_faceit_ranking(player_stats)

    return embed


# Funkcja do pobierania szczegółowych statystyk meczu
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

async def get_last_match_stats(nickname):
    player_data = get_faceit_player_data(nickname)
    if not player_data:
        return f'❌ Nie znaleziono gracza o nicku **{nickname}** na Faceit.'

    player_id = player_data['player_id']
    player_nickname = player_data['nickname']
    avatar_url = player_data.get('avatar', 'https://www.faceit.com/static/img/avatar.png')

    matches = get_faceit_player_matches(player_id)
    if not matches or len(matches) == 0:
        return f'❌ Nie udało się pobrać danych o meczach gracza **{player_nickname}**.'

    last_match = matches[0]
    match_id = last_match["stats"].get("Match Id")

    if not match_id:
        return f'❌ Nie udało się znaleźć match_id w danych gracza **{nickname}**.\n🔍 Debug: {last_match}'

    # Pobranie wyniku meczu
    result = last_match["stats"].get("Result", "Brak danych")
    if result == "1":
        match_result = "✅"
    elif result == "0":
        match_result = "❌"
    else:
        match_result = "❓"

    match_stats = get_faceit_match_details(match_id)
    if not match_stats:
        return f'❌ Nie udało się pobrać szczegółowych danych o meczu.'

    map_name = match_stats.get("map", "Nieznana").replace("de_", "")

    embed = discord.Embed(
        title=f"**Ostatni mecz gracza {player_nickname}**",
        description=f"**Mapa:** {map_name} | {match_result}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=avatar_url)

    total_kills, total_deaths, total_assists, total_hs, total_kd = 0, 0, 0, 0, 0
    match_summary = "```"
    match_summary += f"{'Gracz'.ljust(20)} {'🔪 K/D/A'.ljust(12)} {'🎯 HS'.ljust(5)} {'K/D'.ljust(5)}\n"
    match_summary += "-" * 45 + "\n"

    player_team = None  # Zmienna do przechowywania drużyny gracza

    # Wyszukaj drużynę, w której gra wyszukiwany gracz
    for team_name, team_data in match_stats["teams"].items():
        for player in team_data["players"]:
            if player["nickname"] == player_nickname:
                player_team = team_name
                break
        if player_team:
            break

    # Jeżeli znaleziono drużynę gracza, wyświetl tylko sojuszników
    if player_team:
        # Tworzymy listę do przechowywania danych graczy
        players_list = []

        for team_name, team_data in match_stats["teams"].items():
            if team_name == player_team:  # Tylko sojusznicy gracza
                for player in team_data["players"]:
                    kills = player.get("kills", 0)
                    deaths = player.get("deaths", 0)
                    assists = player.get("assists", 0)
                    hs = player.get("headshots", 0)

                    total_kills += kills
                    total_deaths += deaths
                    total_assists += assists
                    total_hs += hs

                    # Wyliczanie K/D
                    kd_ratio = kills / deaths if deaths > 0 else kills  # Unikamy dzielenia przez 0
                    total_kd += kd_ratio

                    # Dodajemy gracza do listy jako słownik
                    players_list.append({
                        "nickname": player["nickname"],
                        "kills": kills,
                        "deaths": deaths,
                        "assists": assists,
                        "hs": hs,
                        "kd_ratio": kd_ratio
                    })

        # Sortujemy listę graczy według liczby zabójstw (malejąco)
        players_list.sort(key=lambda x: x["kills"], reverse=True)

        # Generujemy podsumowanie po posortowaniu
        for player in players_list:
            stats = f"{player['kills']}/{player['deaths']}/{player['assists']}"
            if player["nickname"] == player_nickname:
                match_summary += f"{player['nickname'].ljust(20)} {stats.ljust(12)} {str(player['hs']).ljust(5)} {player['kd_ratio']:.2f}\n"
            else:
                match_summary += f"{player['nickname'].ljust(20)} {stats.ljust(12)} {str(player['hs']).ljust(5)} {player['kd_ratio']:.2f}\n"

    match_summary += "```"

    embed.add_field(
        name=f"📊 Statystyki gracza {nickname} i drużyny",
        value=match_summary if match_summary else "Brak danych",
        inline=False
    )

    # Zamiast średnich statystyk, podaj link do meczu
    match_link = f"https://www.faceit.com/en/csgo/match/{match_id}"

    embed.add_field(
        name="🔗 Link do lobby",
        value=f"[Kliknij]({match_link})",
        inline=False
    )

    embed.set_footer(text="📊 Statystyki ostatniego meczu | Sprawdź swoje pod !last [nick]")

    return embed





