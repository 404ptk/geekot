import requests
import json
import discord

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
        print("Faceit API:", response.json())
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