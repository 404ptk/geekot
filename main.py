import random

import discord
import requests
import os
import re


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
TWITCH_CLIENT_ID = load_token('twitch_client_id.txt')
TWITCH_CLIENT_SECRET = load_token('twitch_client_secret.txt')

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

# Inicjalizacja listy wymówek
wymowki = [
]

# Dodajemy funkcję do zapisywania wymówek do pliku
WYMOWKI_FILE = "wymowki.txt"


def save_wymowki():
    with open(WYMOWKI_FILE, "w", encoding="utf-8") as file:
        for line in wymowki:
            file.write(line + "\n")


# Dodajemy funkcję do wczytywania wymówek z pliku
def load_wymowki():
    if os.path.exists(WYMOWKI_FILE):
        with open(WYMOWKI_FILE, "r") as file:
            for line in file:
                wymowki.append(line.strip())


# Wczytujemy wymówki przy starcie bota
load_wymowki()

# Inicjalizacja listy wyzwań
challenges = []

# Plik do przechowywania wyzwań
CHALLENGES_FILE = "challenges.txt"

# Funkcja do zapisywania wyzwań do pliku
def save_challenges():
    with open(CHALLENGES_FILE, "w", encoding="utf-8") as file:
        for challenge in challenges:
            file.write(challenge + "\n")

# Funkcja do wczytywania wyzwań z pliku
def load_challenges():
    if os.path.exists(CHALLENGES_FILE):
        with open(CHALLENGES_FILE, "r", encoding="utf-8") as file:
            for line in file:
                challenges.append(line.strip())
    else:
        # Domyślne wyzwania na start
        default_challenges = [
            "Zagraj rundę tylko z Deagle",
            "Wygraj mecz bez kupowania granatów",
            "Użyj tylko noża w jednej rundzie",
            "Zabij 3 przeciwników z AWP w jednym meczu"
        ]
        challenges.extend(default_challenges)
        save_challenges()

# Wczytanie wyzwań przy starcie bota
load_challenges()

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

    # Sortowanie według ELO i poziomu
    player_stats.sort(key=lambda x: (x['elo'], x['level']), reverse=True)

    # Tworzenie embeda
    embed = discord.Embed(
        title="📊 **Ranking Faceit**",
        description="🔹 Lista graczy uszeregowana według ELO i poziomu CS2.",
        color=discord.Color.blue()
    )

    # Dodanie graczy do embeda
    for index, player in enumerate(player_stats):
        rank_emoji = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else "🎮"
        flag = "🇺🇦" if player['nickname'] == "PhesterM9" else "🇵🇱"

        embed.add_field(
            name=f"{rank_emoji} **{player['nickname']}** {flag}",
            value=f"**ELO**: {player['elo']} | **LVL**: {player['level']}",
            inline=False
        )

    # Stopka i dodatkowe info
    embed.set_footer(text="📅 Ranking generowany automatycznie")

    return embed

# Obsługa zdarzenia - gdy bot jest gotowy
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    await client.change_presence(activity=discord.Game(name="!geek - Jestem geekiem"))


# Funkcja do wyświetlania ostatniego meczu gracza `-Masny-`
async def display_last_match_stats():
    nickname = "-Masny-"
    player_data = get_faceit_player_data(nickname)

    if player_data is None:
        return f'Nie znaleziono gracza o nicku {nickname} na Faceit.'

    player_id = player_data['player_id']
    player_nickname = player_data['nickname']
    matches = get_faceit_player_matches(player_id)

    if not matches:
        return f'Nie udało się pobrać danych o meczach gracza {player_nickname}.'

    # Tylko pierwszy (ostatni) mecz z listy
    last_match = matches[0]

    # Szczegóły meczu
    map_name = last_match.get('stats', {}).get('Map', 'Nieznana').replace('de_', '')
    result = 'W' if last_match.get('stats', {}).get('Result') == '1' else 'L'
    kills = int(last_match.get('stats', {}).get('Kills', 0))
    deaths = int(last_match.get('stats', {}).get('Deaths', 0))
    assists = int(last_match.get('stats', {}).get('Assists', 0))
    hs = int(last_match.get('stats', {}).get('Headshots %', 0))

    # Formatowanie odpowiedzi
    # last_match_stats = f'**Ostatni mecz gracza {player_nickname}:**\n'
    last_match_stats = f'**Mapa**: {map_name}\n'
    last_match_stats += f'**Wynik**: {result}\n'
    last_match_stats += f'**K/D/A**: {kills}/{deaths}/{assists}\n'
    last_match_stats += f'**HS%**: {hs}%\n'

    return last_match_stats

def get_twitch_access_token():
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"Błąd podczas uzyskiwania tokena Twitch: {response.status_code}")
        return None

def get_twitch_stream_data(username):
    access_token = get_twitch_access_token()
    if not access_token:
        return None

    url = 'https://api.twitch.tv/helix/streams'
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'user_login': username.lower()
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json().get('data', [])
        if data:  # Stream jest aktywny
            stream = data[0]
            thumbnail_url = stream['thumbnail_url'].replace('{width}', '1280').replace('{height}', '720')
            return {'live': True, 'thumbnail_url': thumbnail_url, 'title': stream['title']}
        else:  # Stream offline, pobieramy dane kanału
            return get_twitch_channel_data(username, access_token)
    else:
        print(f"Błąd API Twitch: {response.status_code}")
        return None

def get_twitch_channel_data(username, access_token):
    url = 'https://api.twitch.tv/helix/channels'
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'broadcaster_login': username.lower()
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json().get('data', [])
        if data:
            # Twitch nie dostarcza ostatniej klatki wprost, ale możemy użyć domyślnego obrazu offline lub profilu
            return {'live': False, 'thumbnail_url': None, 'title': 'Offline'}
    return None

# Obsługa wiadomości użytkowników
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.author.name.lower() == "phester102":
        await message.add_reaction("🥶")  # Dodanie reakcji :cold_face:

    if message.content.startswith('!geek'):
        embed = discord.Embed(
            title="📜 Dostępne komendy",
            description="Lista komend dostępnych na serwerze:",
            color=discord.Color.blue()
        )

        embed.add_field(name="🎮 **Faceit**", value="`!faceit [nick]` - Statystyki profilu [nick]\n"
                                                   "`!discordfaceit` - Statystyki discorda na Faceicie", inline=False)

        embed.add_field(name="📊 **Tabela Masnego**", value="`!masny` - Tabela Masnego\n"
                                                           "`!masny [1-5]` - Zajęte miejsce w tabeli\n"
                                                           "`!masny -1` - Odejmowanie miejsca 1 w tabeli", inline=False)

        embed.add_field(name="🎭 **Wymówki Masnego**", value="`!dodajwymowke` - Dodawanie wymówek\n"
                                                            "`!losujwymowke` - Losowanie wymówek\n"
                                                            "`!wymowki` - Lista wymówek", inline=False)

        embed.add_field(name="🚀 **Spawn Masnego**", value="`!spawn` - Spawn Masnego\n"
                                                          "`!spawn [godzina]` - Można wpisać np. `!spawn 16`",
                        inline=False)
        embed.add_field(name="🎥 **Stan streamera**", value="`!stan [H2P_Gucio]` - Pokazuje ostatnią/aktualną klatkę ze streama", inline=False)

        embed.add_field(name="🎯 **CS2 Instanty**", value="`!instant` - Lista dostępnych instantów (CS2)", inline=False)

        embed.add_field(name="🔥 **Challenges CS2**",
                        value="`!wyzwanie` - Losuje wyzwanie z listy challengów\n"
                              "`!dodajwyzwanie` - Dodaj wyzwanie do listy challengów\n"
                              "`!wyzwania` - Lista dostępnych challengów", inline=False)

        embed.set_footer(text="Geekot - Jestem geekiem, największym geekiem 🎮")

        await message.channel.send(embed=embed)

    # Komenda !losujwymowke
    if message.content.startswith('!losujwymowke'):
        wymowka = random.choice(wymowki)  # Losowy wybór wymówki z listy
        await message.channel.send(f"Wymówka masnego: {wymowka}")

    # Komenda !dodajwymowke <tekst>
    if message.content.startswith('!dodajwymowke'):
        parts = message.content.split(" ", 1)
        if len(parts) < 2:
            await message.channel.send(
                "Podaj tekst wymówki, np. `!dodajwymowke za tluste lapy.` **(BEZ POLSKICH ZNAKÓW)**")
        else:
            nowa_wymowka = parts[1].strip()
            wymowki.append(nowa_wymowka)  # Dodanie nowej wymówki do listy
            save_wymowki()  # Zapisanie nowej wymówki do pliku
            await message.channel.send(f"Dodano nową wymówkę: {nowa_wymowka}")

    # Nowa komenda do wyświetlania wszystkich zapisanych wymówek
    if message.content.startswith('!wymowki'):
        if not wymowki:
            embed = discord.Embed(
                title="🎭 Lista wymówek Masnego",
                description="Brak zapisanych wymówek. Dodaj jedną za pomocą `!dodajwymowke`!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Zapisz wymówki masnego!")
            await message.channel.send(embed=embed)
        else:
            wymowki_list = "\n".join(f"{i + 1}. {wymowka}" for i, wymowka in enumerate(wymowki))
            embed = discord.Embed(
                title="🎭 Lista wymówek Masnego",
                description=f"Oto wszystkie zapisane wymówki:\n{wymowki_list}",
                color=discord.Color.purple()
            )
            embed.set_footer(text=f"Liczba wymówek: {len(wymowki)} | Losuj jedną za pomocą `!losujwymowke`")
            await message.channel.send(embed=embed)

    # Komenda !instant
    if message.content.startswith("!instant"):
        await message.channel.send("Dostępne mapy:\n"
                                   "- !mirage\n"
                                   "- !anubis\n"
                                   "- !ancient")

    # Komenda !ancient
    if message.content.startswith('!ancient'):
        image_url_ancient_t_spawn = "https://cdn.discordapp.com/attachments/809156611167748176/1340790953237151754/ancient_instant_mid_smokes.png?ex=67b3a461&is=67b252e1&hm=d51938f2610cb3ea9c4947000d0bc636d3633f99749b0e193f00d563eb4962e4&"
        image_url_ancient_ct_spawn = "https://cdn.discordapp.com/attachments/809156611167748176/1340790762635399198/ancient_instant_elbow_smokes.png?ex=67b3a434&is=67b252b4&hm=5a3b52d428f353172ce9603d9b0d8dfeab40722f211eeae22705bc1f0697bad2&"
        await message.channel.send("Instant smokes mid from T spawn")
        await message.channel.send(image_url_ancient_t_spawn)
        await message.channel.send("Instant smokes elbow from CT spawn")
        await message.channel.send(image_url_ancient_ct_spawn)

    # Komenda !mirage
    if message.content.startswith('!mirage'):
        image_url_mirage_t_spawn = "https://cdn.discordapp.com/attachments/809156611167748176/1340791024842309652/mirage_instant_smokes.png?ex=67b3a473&is=67b252f3&hm=addbb5838df74336b88b20d87655daeba80429fad8fa2163721fa0423228e3e0&"
        await message.channel.send("Instant smokes mid from T spawn")
        await message.channel.send(image_url_mirage_t_spawn)

    # Komenda !anubis
    if message.content.startswith('!anubis'):
        image_url_anubis_ct_spawn = "https://cdn.discordapp.com/attachments/1301248598108798996/1340782160701030474/image.png?ex=67b39c31&is=67b24ab1&hm=38bd2843da71955749891f1659c81b48c60287c306bf94abdb1adc06a5a2def0&"
        await message.channel.send("Instant smokes mid from CT spawn")
        await message.channel.send(image_url_anubis_ct_spawn)

    # Komenda !discordfaceit do wyświetlania statystyk
    if message.content.startswith('!discordfaceit'):
        embed = await get_discordfaceit_stats()
        await message.channel.send(embed=embed)

    if message.content.startswith('!spawn'):
        user_id = 606785554918539275  # ID użytkownika mansy_
        user = await client.fetch_user(user_id)  # Pobieramy użytkownika

        args = message.content.split()  # Dzielimy wiadomość na części

        if len(args) == 1:
            # Jeśli nie podano dodatkowego argumentu
            await message.channel.send(f"Klucha wbijaj na csa potrzebujemy cie w naszym składzie {user.mention}")
        elif len(args) == 2:
            if re.match(r"^\d{2}:\d{2}$", args[1]):
                # Jeśli podano czas w formacie HH:MM
                await message.channel.send(f"Klucha, wołają cię na csa o {args[1]} {user.mention}")
            elif re.match(r"^\d{1,2}$", args[1]):
                # Jeśli podano czas w formacie HH (np. 16 zamiast 16:00)
                await message.channel.send(f"Klucha, wołają cię na csa o {args[1]}:00 {user.mention}")
            else:
                # Jeśli podano niepoprawny format
                await message.channel.send("Niepoprawny format - poprawny: !spawn 16:00 lub !spawn 16")

    # Komenda do pobierania danych z Faceit

    if message.content.startswith('!faceit'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send('Podaj nick gracza Faceit, np. `!faceit Nick`')
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

            if result == '1':
                result_display = '✅'
                total_wins += 1
            elif result == '0':
                result_display = '❌'
            else:
                result_display = '❓'

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

            match_summary += f"{map_name.ljust(15)} {result_display.ljust(5)} {f'{kills}/{deaths}/{assists}'.ljust(9)} {f'{hs}%'.ljust(5)} {adr:.0f}\n"

        match_summary += "```"

        embed.add_field(
            name="🎮 Ostatnie 5 meczów",
            value=match_summary if match_summary else "Brak danych",
            inline=False
        )

        avg_kills = int(total_kills / match_count) if match_count > 0 else 0
        avg_deaths = int(total_deaths / match_count) if match_count > 0 else 0
        avg_assists = int(total_assists / match_count) if match_count > 0 else 0
        avg_hs = total_hs / match_count if match_count > 0 else 0
        win_percentage = (total_wins / match_count) * 100 if match_count > 0 else 0
        avg_kd = float(avg_kills / avg_deaths) if match_count > 0 and avg_deaths > 0 else 0
        avg_adr = float(total_adr / match_count) if match_count > 0 else 0

        embed.add_field(
            name="📊 Średnie statystyki",
            value=f"**K/D:** {avg_kd:.2f} | **HS:** {avg_hs:.0f}% | **ADR:** {avg_adr:.1f}\n**Winrate:** {win_percentage:.0f}%",
            inline=False
        )

        await message.channel.send(embed=embed)

    # Słownik z linkami do zdjęć w zależności od zajętego miejsca
    image_links = {
        "1": "https://cdn.discordapp.com/attachments/809156611167748176/1330901097816129596/BE8227A4-FD7F-42E4-A48F-350CD124D92B.png?ex=678fa9bc&is=678e583c&hm=ac937a4d34a9375cc56fefdbb1d228733a3fdf0daaaa720e5a020ecd302a878e&",
        "2": "https://cdn.discordapp.com/attachments/809156611167748176/1330905145772474428/61A0B076-BD51-400C-AF19-A7B1D626B1B1.png?ex=678fad81&is=678e5c01&hm=6f06532e17ca3e49d550adc2cf84ff19f80b91e5b7b8833c7c7dc54061f40882&",
        "3": "https://cdn.discordapp.com/attachments/809156611167748176/1330911802049036340/2698389E-237A-4840-8A63-07F996640858.png?ex=678fb3b4&is=678e6234&hm=4870f7636f0053600f02e59e2c9332c5c0272d04e8cb25d25ad643c6f2947739&",
        "4": "https://media.discordapp.net/attachments/778302928338550865/1300471813146415176/B4B5C4D4-8E00-43CE-927B-E9CC47FB2201.png?ex=678fb441&is=678e62c1&hm=661a9436fdf6bbe526df0afa62a28adf1ae8a4dbca4dab0f333d4a4c059d9a0d&=&format=webp&quality=lossless&width=359&height=601",
        "5": "https://cdn.discordapp.com/attachments/809156611167748176/1330906894302318592/pobrane_1.gif?ex=678faf22&is=678e5da2&hm=908f4934957c128b1531edc28da1820b096fd8a1bd35358621e794336969884e&"
    }

    if message.content.startswith('!masny'):
        parts = message.content.split()

        # Obsługa komendy w formacie "!masny X", gdzie X to liczba od 1 do 5
        if len(parts) == 2 and parts[1] in masny_counter:
            masny_counter[parts[1]] += 1
            save_masny_data()  # Zapisanie stanu po każdej zmianie

            # Pobranie tabeli z ostatniego meczu -Masny-
            last_match_stats = await display_last_match_stats()

            # Wybór odpowiedniego zdjęcia na podstawie wybranego miejsca
            image_url = image_links.get(parts[1],
                                        "https://cdn.discordapp.com/avatars/606785554918539275/f9528561e91c8c742e6b45ddcf9dd82c.png?size=1024")

            embed = discord.Embed(
                title=f"🏆 Masny zajął {parts[1]} miejsce!",
                color=discord.Color.gold()
            )
            embed.set_image(url=image_url)
            embed.add_field(name="📊 Statystyki ostatniego meczu", value=last_match_stats, inline=False)

            await message.channel.send(embed=embed)

        # Obsługa komendy w formacie "!masny -X", gdzie X to liczba od 1 do 5 (usunięcie miejsca)
        elif len(parts) == 2 and parts[1].startswith('-') and parts[1][1:] in masny_counter:
            place = parts[1][1:]
            if masny_counter[place] > 0:
                masny_counter[place] -= 1
                save_masny_data()  # Zapisanie stanu po każdej zmianie
                embed = discord.Embed(
                    title="📉 Aktualizacja tabeli Masnego",
                    description=f"Miejsce **{place}** zostało zmniejszone o 1.",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Błąd",
                    description=f"Miejsce **{place}** jest już na zerze i nie można go dalej zmniejszać.",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)

        # Jeśli komenda to tylko "!masny" - wyświetl statystyki
        elif len(parts) == 1:
            total_counts = sum(masny_counter.values())

            # Wyznaczanie średniego miejsca
            if total_counts > 0:
                weighted_sum = sum(int(key) * count for key, count in masny_counter.items())
                avg_position = weighted_sum / total_counts
            else:
                avg_position = 0

            # Wyznaczanie najczęściej zajmowanego miejsca (zaokrąglone do najbliższej liczby całkowitej)
            if total_counts > 0:
                # rounded_avg = round(avg_position)
                most_common_position = max(masny_counter, key=masny_counter.get)
            else:
                most_common_position = None
                # rounded_avg = None

            # Budowanie embed z wynikami
            embed = discord.Embed(
                title="📊 Miejsca w tabeli Masnego",
                color=discord.Color.blue()
            )

            for key in sorted(masny_counter.keys()):  # Sortujemy klucze miejsc od 1 do 5
                count = masny_counter[key]
                percent = (count / total_counts) * 100 if total_counts > 0 else 0
                embed.add_field(name=f"🏅 **{key} miejsce**", value=f"{count} razy *({percent:.2f}%)*", inline=False)

            # Dodanie informacji o średnim miejscu i najczęściej zajmowanym miejscu
            embed.add_field(name="\n", value="", inline=False)
            embed.add_field(name="📉 Średnie miejsce", value=f"**{avg_position:.2f}**", inline=False)
            embed.add_field(name="📌 Masny najczęściej zajmuje", value=f"**{most_common_position}** miejsce", inline=False)
            embed.add_field(name="\n", value="", inline=False)

            embed.set_footer(text="Aby dopisać miejsce Masnego w tabeli wpisz `!masny [miejsce]`")

            await message.channel.send(embed=embed)

    if message.content.startswith('!stan'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("Podaj nazwę użytkownika Twitch, np. `!stan Cinkrofwest`")
            return

        username = parts[1]
        stream_data = get_twitch_stream_data(username)

        if stream_data is None:
            await message.channel.send(f"Nie udało się pobrać danych dla użytkownika {username}.")
            return

        embed = discord.Embed(
            title=f"Stan streama {username}",
            color=discord.Color.purple()
        )

        if stream_data['live']:
            embed.description = f"**{username} jest na żywo!**\n*{stream_data['title']}*"
            embed.set_image(url=stream_data['thumbnail_url'])
        else:
            embed.description = f"**{username} jest offline.**"
            # Jeśli nie ma miniaturki, możesz użyć domyślnego obrazu lub pominąć set_image
            if stream_data['thumbnail_url']:
                embed.set_image(url=stream_data['thumbnail_url'])
            else:
                embed.set_image(
                    url="https://static-cdn.jtvnw.net/ttv-static/404_preview-1280x720.jpg")  # Domyślny obraz offline Twitcha

        embed.add_field(
            name="",
            value=f"[{username}](https://twitch.tv/{username})",
            inline=False
        )
        await message.channel.send(embed=embed)

    # Komenda !challenge - losowanie wyzwania
    if message.content.startswith('!wyzwanie'):
        if not challenges:
            await message.channel.send("Brak zapisanych wyzwań. Dodaj jedno za pomocą `!dodajwyzwanie`!")
        else:
            challenge = random.choice(challenges)
            embed = discord.Embed(
                title="🎯 Twoje wyzwanie CS2",
                description=f"**{challenge}**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Powodzenia! Dodaj własne wyzwanie za pomocą `!dodajwyzwanie`")
            await message.channel.send(embed=embed)

    # Komenda !addchallenge - dodawanie nowego wyzwania
    if message.content.startswith('!dodajwyzwanie'):
        parts = message.content.split(" ", 1)
        if len(parts) < 2:
            await message.channel.send("Podaj treść wyzwania, np. `!dodajwyzwanie Zagraj tylko z nożem`")
        else:
            new_challenge = parts[1].strip()
            challenges.append(new_challenge)
            save_challenges()  # Zapisanie do pliku
            embed = discord.Embed(
                title="✅ Nowe wyzwanie dodane!",
                description=f"Dodałeś: **{new_challenge}**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Spróbuj je wylosować za pomocą `!wyzwanie`")
            await message.channel.send(embed=embed)

    # Komenda !challenges - wyświetlanie listy wszystkich wyzwań
    if message.content.startswith('!wyzwania'):
        if not challenges:
            await message.channel.send("Brak zapisanych wyzwań. Dodaj jedno za pomocą `!dodajwyzwanie`!")
        else:
            challenges_list = "\n".join(f"{i + 1}. {challenge}" for i, challenge in enumerate(challenges))
            embed = discord.Embed(
                title="📋 Lista wyzwań CS2",
                description=f"Oto dostępne wyzwania:\n{challenges_list}",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Użyj `!wyzwanie`, aby wylosować jedno z nich!")
            await message.channel.send(embed=embed)

# Uruchomienie bota
client.run(DISCORD_TOKEN)
