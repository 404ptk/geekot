import discord
import requests
import os

# Funkcja do wczytania tokena z pliku
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

# Wczytanie tokenów
DISCORD_TOKEN = load_token('discord_token.txt')
FACEIT_API_KEY = load_token('faceit_api.txt')

# Tworzenie klienta Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Plik do przechowywania danych
MASNY_FILE = "masny.txt"

# Słownik do przechowywania liczby użyć komend !masny
masny_counter = {
    "1": 0,
    "2": 0,
    "3": 0,
    "4": 0,
    "5": 0
}

# Funkcja do zapisywania danych do pliku
def save_masny_data():
    with open(MASNY_FILE, "w") as file:
        for key, count in masny_counter.items():
            file.write(f"{key} {count}\n")

# Funkcja do wczytywania danych z pliku
def load_masny_data():
    # Sprawdzanie, czy plik istnieje
    if not os.path.exists(MASNY_FILE):
        save_masny_data()  # Inicjalizacja pliku z zerowymi wartościami

    # Wczytywanie danych z pliku i walidacja formatu danych
    with open(MASNY_FILE, "r") as file:
        for line in file:
            try:
                key, count = line.strip().split()
                if key in masny_counter:  # Sprawdzanie, czy klucz jest prawidłowy
                    masny_counter[key] = int(count)
            except ValueError:
                print(f"Błąd przy wczytywaniu linii: {line}")

# Wczytanie danych przy starcie bota
load_masny_data()

# Lista pseudonimów graczy
player_nicknames = ['utopiasz', 'radzioswir', 'PhesterM9', '-Masny-',
                    'vazil1103', 'Kvzia', 'Kajetov', 'nawzea', 'BEJLI', 'MlodyHubii']


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

# Funkcja do pobierania statystyk dla graczy w Discordzie
async def get_discordfaceit_stats():
    player_stats = []

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

    # Sortowanie listy według ELO i LVL od najwyższego do najmniejszego
    player_stats.sort(key=lambda x: (x['elo'], x['level']), reverse=True)

    # Generowanie wiadomości z wynikami
    message_content = "**Statystyki **\n\n"
    for player in player_stats:
        message_content += f"**{player['nickname']}** - ELO: {player['elo']}, LVL: {player['level']}\n"

    return message_content

# Obsługa zdarzenia - gdy bot jest gotowy
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    await client.change_presence(activity=discord.Game(name="!geek - Jestem geekiem"))

# Obsługa wiadomości użytkowników
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Komenda !geek do wyświetlania help deska
    if message.content.startswith('!geek'):
        message_content = "Dostępne komendy:\n" \
                          "``!faceit [nick]`` - Statystyki profilu [nick]\n" \
                          "``!discordfaceit`` - Statystyki discorda na faceicie\n" \
                          "``!masny`` - Tabela masnego\n" \
                          "``!masny [1-5]`` - Zajęte miejsce w tabeli przez masnego"
        await message.channel.send(message_content)

    # Komenda !discordfaceit do wyświetlania statystyk
    if message.content.startswith('!discordfaceit'):
        message_content = await get_discordfaceit_stats()
        await message.channel.send(message_content)

    # Komenda do pobierania danych z Faceit
    if message.content.startswith('!faceit'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send('Podaj nick gracza Faceit, np. ``!faceit Nick.``')
            return

        nickname = parts[1]
        player_data = get_faceit_player_data(nickname)
        if player_data is None:
            await message.channel.send(f'Nie znaleziono gracza o nicku {nickname} na Faceit.')
            return

        player_id = player_data['player_id']
        player_nickname = player_data['nickname']
        matches = get_faceit_player_matches(player_id)
        if matches is None:
            await message.channel.send(f'Nie udało się pobrać danych o meczach gracza {player_nickname}.')
            return

        player_level = player_data.get('games', {}).get('cs2', {}).get('skill_level', "Brak danych")
        player_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', 'Brak danych')
        player_info = f'LVL: {player_level}\t | \t ELO: {player_elo}'

        message_content = '**' + player_nickname + '**' + "\t | \t " + player_info
        message_content += f'\n\nOstatnie 5 meczów gracza {player_nickname}:\n'
        # Nagłówki dla kolumn
        message_content += f'{"**Mapa**":<30}{"**Wynik**":<30}{"**K/D/A**":<40}{"**HS**":<30}\n'

        # Inicjalizacja sum dla średnich i licznik wygranych
        total_kills, total_deaths, total_assists, total_hs, total_wins = 0, 0, 0, 0, 0
        match_count = len(matches)

        for match in matches:
            map_name = match.get('stats', {}).get('Map', 'Nieznana').replace('de_', '')
            result = match.get('stats', {}).get('Result', 'Brak danych')

            # Przypisanie wartości do wyników i liczenie wygranych
            if result == '1':
                result_display = 'W'
                total_wins += 1
            elif result == '0':
                result_display = 'L'
            else:
                result_display = 'Brak danych'

            kills = int(match.get('stats', {}).get('Kills', 0))  # Konwersja na int dla obliczeń
            deaths = int(match.get('stats', {}).get('Deaths', 0))
            assists = int(match.get('stats', {}).get('Assists', 0))
            hs = int(match.get('stats', {}).get('Headshots %', 0))

            # Sumowanie statystyk
            total_kills += kills
            total_deaths += deaths
            total_assists += assists
            total_hs += hs

            # Formatowanie wyjścia
            message_content += f'{map_name:<30}{result_display:<30}{kills}/{deaths}/{assists:<30}{hs}%\n'

        # Obliczanie średnich i procentu wygranych
        avg_kills = int(total_kills / match_count) if match_count > 0 else 0
        avg_deaths = int(total_deaths / match_count) if match_count > 0 else 0
        avg_assists = int(total_assists / match_count) if match_count > 0 else 0
        avg_hs = total_hs / match_count if match_count > 0 else 0
        win_percentage = (total_wins / match_count) * 100 if match_count > 0 else 0
        avg_kd = float(avg_kills / avg_deaths) if match_count > 0 else 0

        # Dodanie średnich i procentu wygranych do wiadomości
        message_content += f'\n**Średnia statystyk**:\n-# K/D: *{avg_kd:.2f}* \t | \t HS: *{avg_hs}%*\n'
        message_content += f'-# Procent wygranych ostatnich 5 meczy: *{win_percentage}%*'
        message_content += f' \n-# [Profil](<https://faceit.com/pl/players/{player_nickname}>)'

        await message.channel.send(message_content)

    # Obsługa komend !masny
    if message.content.startswith('!masny'):
        parts = message.content.split()

        # Obsługa komendy w formacie "!masny X", gdzie X to liczba od 1 do 5 (dodanie miejsca)
        if len(parts) == 2 and parts[1] in masny_counter:
            masny_counter[parts[1]] += 1
            save_masny_data()  # Zapisanie stanu po każdej zmianie
            await message.channel.send(
                f'Masny zajął {parts[1]} miejsce.\nhttps://cdn.discordapp.com/avatars/606785554918539275/f9528561e91c8c742e6b45ddcf9dd82c.png?size=1024')

        # Obsługa komendy w formacie "!masny -X", gdzie X to liczba od 1 do 5 (usunięcie miejsca)
        elif len(parts) == 2 and parts[1].startswith('-') and parts[1][1:] in masny_counter:
            place = parts[1][1:]
            if masny_counter[place] > 0:
                masny_counter[place] -= 1
                save_masny_data()  # Zapisanie stanu po każdej zmianie
                await message.channel.send(f'Miejsce {place} zostało zmniejszone o 1.')
            else:
                await message.channel.send(f'Miejsce {place} jest już na zerze i nie można go dalej zmniejszać.')

        # Jeśli komenda to tylko "!masny" - wyświetl statystyki
        elif len(parts) == 1:
            total_counts = sum(masny_counter.values())

            # Wyznaczanie najczęściej używanej komendy
            if total_counts > 0:
                most_common = max(masny_counter, key=masny_counter.get)
                most_common_count = masny_counter[most_common]
                most_common_percent = (most_common_count / total_counts) * 100
            else:
                most_common = None
                most_common_count = 0
                most_common_percent = 0

            # Budowanie komunikatu z wynikami
            scoreboard = "**Miejsca w tabeli Masnego:**\n"
            for key in sorted(masny_counter.keys()):  # Sortujemy klucze miejsc od 1 do 5
                count = masny_counter[key]
                percent = (count / total_counts) * 100 if total_counts > 0 else 0
                scoreboard += f"**{key} miejsce** - {count} razy *({percent:.2f}%)*\n"

            # Średnia liczba użyć i najczęściej wybierana komenda z procentem
            average = total_counts / len(masny_counter) if len(masny_counter) > 0 else 0
            scoreboard += f"\nMasny najczęściej jest **{most_common}** w tabeli (*{most_common_count} razy - {most_common_percent:.2f}%)*\n"

            await message.channel.send(
                scoreboard + "Aby dopisać miejsce masnego w tabeli wpisz ``!masny [miejsce]``")


# Uruchomienie bota
client.run(DISCORD_TOKEN)
