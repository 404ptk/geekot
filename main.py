import random
from datetime import date

import discord
import requests
import os
import re
from discord.ext import commands
import json

from twitch_utils import *
from masny_utils import *
from faceit_utils import *


# from soundcloud_utils import *


# TODO:
# dodać wynik meczu przy !last (tzn. np 13:10)

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
DISCORD_TOKEN = load_token('txt/discord_token.txt')
FACEIT_API_KEY = load_token('txt/faceit_api.txt')
TWITCH_CLIENT_ID = load_token('txt/twitch_client_id.txt')
TWITCH_CLIENT_SECRET = load_token('txt/twitch_client_secret.txt')

# Tworzenie klienta Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Inicjalizacja listy wyzwań
challenges = []

# Plik do przechowywania wyzwań
CHALLENGES_FILE = "txt/challenges.txt"


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

reaction_name = "phester102"
reaction_active = False


def save_reaction_state():
    with open('txt/reaction_state.json', 'w') as f:
        json.dump({'reaction_active': reaction_active}, f)


def load_reaction_state():
    global reaction_active
    try:
        with open('txt/reaction_state.json', 'r') as f:
            data = json.load(f)
            reaction_active = data.get('reaction_active', False)
    except FileNotFoundError:
        reaction_active = False


GAMES_FILE = "txt/gry.json"
games = []


def load_games():
    """Wczytuje listę gier z pliku JSON."""
    if os.path.exists(GAMES_FILE):
        with open(GAMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return []


def save_games():
    """Zapisuje listę gier do pliku JSON."""
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=4, ensure_ascii=False)


# Wczytanie gier przy starcie bota
games = load_games()

REFERENCE_DATE_FILE = "txt/days_reference.txt"

def load_reference_date():
    """
    Wczytuje datę odniesienia z pliku.
    Jeżeli plik nie istnieje, tworzy go z domyślną datą 02.11.2024.
    """
    if not os.path.exists(REFERENCE_DATE_FILE):
        # Tworzymy plik z domyślną datą 2024-11-02
        with open(REFERENCE_DATE_FILE, 'w', encoding="utf-8") as f:
            f.write("2024-11-02")
        return date(2024, 11, 2)
    else:
        with open(REFERENCE_DATE_FILE, 'r', encoding="utf-8") as f:
            date_str = f.read().strip()
            # Zakładamy format YYYY-MM-DD (np. "2024-11-02")
            year, month, day = date_str.split("-")
            return date(int(year), int(month), int(day))

def save_reference_date(d: date):
    """
    Zapisuje przekazaną datę odniesienia do pliku.
    """
    with open(REFERENCE_DATE_FILE, 'w', encoding="utf-8") as f:
        f.write(d.isoformat())  # zapisze w formacie YYYY-MM-DD

# Obsługa zdarzenia - gdy bot jest gotowy
@client.event
async def on_ready():
    # send_daily_stats(client)
    load_reaction_state()

    print(f'{client.user} has connected to Discord!\n'
          f'Reacting to {reaction_name}: {reaction_active}')
    await client.change_presence(activity=discord.Game(name="!geek - Jestem geekiem"))


# Obsługa wiadomości użytkowników
@client.event
async def on_message(message):
    global reaction_active
    if message.author == client.user:
        return

    if message.content.startswith('!'):
        if len(message.content) > 1:
            print(f'Uzytkownik {message.author} uzyl komendy {message.content}')

    if message.content.startswith('!plaster'):
        has_high_tier_guard = any(role.name.lower() == "high tier guard" for role in message.author.roles)

        if not has_high_tier_guard:
            await message.channel.send("nice try xd")
            return

        if not reaction_active:
            reaction_active = True
            await message.channel.send(f"Włączono reagowanie na {reaction_name}")
            print(f"Reacting to {reaction_name}: {reaction_active}")
        else:
            reaction_active = False
            await message.channel.send(f"Wyłączono reagowanie na {reaction_name}")
            print(f"Reacting to {reaction_name}: {reaction_active}")

        save_reaction_state()

    if reaction_active and message.author.name.lower() == reaction_name:
        await message.add_reaction("🥶")

    if message.content.startswith(('!geek', '!pomoc', '!help')):
        embed = discord.Embed(
            title="📜 Dostępne komendy",
            description="Lista komend dostępnych na serwerze:",
            color=discord.Color.blue()
        )

        embed.add_field(name="🎮 **Faceit**", value="`!faceit [nick]` - Statystyki profilu [nick]\n"
                                                   "`!discordfaceit` - Statystyki discorda na Faceicie\n"
                                                   "`!last [nick]` - Statystyki drużyny gracza w ostatnim meczu",
                        inline=False)

        embed.add_field(name="📊 **Tabela Masnego**", value="`!masny` - Tabela Masnego\n"
                                                           "`!masny [1-5]` - Zajęte miejsce w tabeli\n"
                                                           "`!masny -1` - Odejmowanie miejsca 1 w tabeli\n"
                                                           "`!resetmasny` - Resetowanie tabeli", inline=False)

        embed.add_field(name="🎭 **Wymówki Masnego**", value="`!dodajwymowke` - Dodawanie wymówek\n"
                                                            "`!losujwymowke` - Losowanie wymówek\n"
                                                            "`!usunwymowke [nr]` - Usuń wymówke z listy\n"
                                                            "`!wymowki` - Lista wymówek", inline=False)

        embed.add_field(name="🚀 **Spawn Masnego**", value="`!spawn` - Spawn Masnego\n"
                                                          "`!spawn [godzina]` - Można wpisać np. `!spawn 16`",
                        inline=False)
        embed.add_field(name="🎥 **Stan streamera**", value="`!stan [H2P_Gucio]` - "
                                                           "Pokazuje ostatnią/aktualną klatkę ze streama", inline=False)

        embed.add_field(name="🎯 **CS2 Instanty**", value="`!instant` - Lista dostępnych instantów (CS2)", inline=False)

        embed.add_field(name="🔥 **Wyzwania CS2**",
                        value="`!wyzwanie` - Losuje wyzwanie z listy challengów\n"
                              "`!dodajwyzwanie` - Dodaj wyzwanie do listy challengów\n"
                              "`!usunwyzwanie [nr]` - Usuń wyzwanie z listy\n"
                              "`!wyzwania` - Lista dostępnych challengów", inline=False)

        embed.add_field(name="🎮 **Gry do zagrania**",
                        value="`!gry` - Lista gier\n"
                              "`!dodajgre [nazwa]` - Dodaj gre do listy\n"
                              "`!dodajopis [nr] [opis]` - Dodaj opis gry\n"
                              "`!edytujopis [nr] [opis]` - Edytuj opis gry\n"
                              "`!usungre [nr]` - Usuń gre z listy")

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

    # Komenda !wymowki i !usunwymowke - wyświetlanie i usuwanie wymówek
    if message.content.startswith('!wymowki') or message.content.startswith('!usunwymowke'):
        if message.content.startswith('!usunwymowke'):
            parts = message.content.split()
            if len(parts) < 2 or not parts[1].isdigit():
                embed = discord.Embed(
                    title="⚠️ Błąd",
                    description="Podaj numer wymówki do usunięcia, np. `!usunwymowke 2`",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
            else:
                index = int(parts[1]) - 1  # Konwersja na indeks (numeracja od 1)
                if 0 <= index < len(wymowki):
                    removed_wymowka = wymowki.pop(index)  # Usunięcie wymówki
                    save_wymowki()  # Aktualizacja pliku
                    embed = discord.Embed(
                        title="✅ Wymówka usunięta",
                        description=f"Usunięto: **{removed_wymowka}**",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text="Sprawdź listę za pomocą `!wymowki`")
                    await message.channel.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="⚠️ Błąd",
                        description=f"Nieprawidłowy numer. Wpisz numer od 1 do {len(wymowki)}",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
        else:  # !wymowki
            if not wymowki:
                embed = discord.Embed(
                    title="🎭 Lista wymówek Masnego",
                    description="Brak zapisanych wymówek. Dodaj jedną za pomocą `!dodajwymowke`!",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Zapisz wymówki Masnego!")
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
        load_masny_data()
        parts = message.content.split()

        # Obsługa komendy w formacie "!masny X", gdzie X to liczba od 1 do 5
        if len(parts) == 2 and parts[1] in masny_counter:
            masny_counter[parts[1]] += 1
            save_masny_data()  # Zapisanie stanu po każdej zmianie
            print(f"Masny took {masny_counter[parts[1]]} place on faceit.")
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
                print(f"Removed one place from {place} place in masny list.")
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
            embed.add_field(name="📌 Masny najczęściej zajmuje", value=f"**{most_common_position}** miejsce",
                            inline=False)
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

    # Komenda !wyzwania i !usunwyzwanie - wyświetlanie i usuwanie wyzwań
    if message.content.startswith('!wyzwanie') or message.content.startswith('!usunwyzwanie'):
        if message.content.startswith('!usunwyzwanie'):
            parts = message.content.split()
            if len(parts) < 2 or not parts[1].isdigit():
                embed = discord.Embed(
                    title="⚠️ Błąd",
                    description="Podaj numer wyzwania do usunięcia, np. `!usunwyzwanie 2`",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
            else:
                index = int(parts[1]) - 1  # Konwersja na indeks (numeracja od 1)
                if 0 <= index < len(challenges):
                    removed_challenge = challenges.pop(index)  # Usunięcie wyzwania
                    save_challenges()  # Aktualizacja pliku
                    print(f"Deleted challenge '{removed_challenge}' from list.")
                    embed = discord.Embed(
                        title="✅ Wyzwanie usunięte",
                        description=f"Usunięto: **{removed_challenge}**",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text="Sprawdź listę za pomocą `!wyzwania`")
                    await message.channel.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="⚠️ Błąd",
                        description=f"Nieprawidłowy numer. Wpisz numer od 1 do {len(challenges)}",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
        else:  # !wyzwania
            if not challenges:
                embed = discord.Embed(
                    title="📋 Lista wyzwań CS2",
                    description="Brak zapisanych wyzwań. Dodaj jedno za pomocą `!dodajwyzwanie`!",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Stwórz swoje wyzwanie!")
                await message.channel.send(embed=embed)
            else:
                challenge = random.choice(challenges)
                embed = discord.Embed(
                    title="🎯 Twoje wyzwanie CS2",
                    description=f"**{challenge}**",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Dodaj własne wyzwanie za pomocą `!dodajwyzwanie`\nPowodzenia!")
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
            print(f"Added challenge '{new_challenge}' to list.")
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

    # if message.content.startswith("!track_stats"):
    #     await send_track_stats(message)

    if message.content.startswith('!last'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("❌ Musisz podać nick gracza! Użycie: `!last <nickname>`")
            return

        nickname = parts[1]
        result = await get_last_match_stats(nickname)

        if isinstance(result, discord.Embed):  # Jeśli funkcja zwróciła Embed
            await message.channel.send(embed=result)
        else:  # Jeśli funkcja zwróciła tekst
            await message.channel.send(result)

    if message.content.startswith("!resetmasny"):
        resetmasny()
        await display_last_match_stats()
        print("Reseted masny.txt file.")
        await message.channel.send("✅ Statystyki w masny.txt zostały zresetowane!\n*Aktualnie z niewiadomych przyczyn "
                                   "plik się resetuje, ale statystyki wyświetlają się stare, po resecie bota będzie "
                                   "poprawna aktualna liczba miejsc.*")

    if message.content.startswith("!dodajgre "):
        game_name = message.content[len("!dodajgre "):].strip()
        if not game_name:
            embed = discord.Embed(
                title="Błąd",
                description="Użycie: `!dodajgre [nazwa gry]`",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        # Dodajemy grę z pustym opisem
        games.append({"name": game_name, "description": ""})
        save_games()
        print(f"Added '{stara_nazwa['name']}' game to list of games to play.")

        # Tworzymy embed z potwierdzeniem
        embed = discord.Embed(
            title="Dodano grę",
            description=f"Pomyślnie dodano **{game_name}** do listy gier.",
            color=discord.Color.blue()
        )
        await message.channel.send(embed=embed)

    if message.content.startswith("!dodajopis "):
        parts = message.content.split(" ", 2)
        if len(parts) < 3:
            embed = discord.Embed(
                title="Błąd",
                description="Użycie: `!dodajopis [numer gry z listy] [opis gry]`",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        index_str = parts[1].strip()
        opis = parts[2].strip()

        if not index_str.isdigit():
            embed = discord.Embed(
                title="Błąd",
                description="Numer gry musi być liczbą!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        index = int(index_str) - 1
        if index < 0 or index >= len(games):
            embed = discord.Embed(
                title="Błąd",
                description="Nieprawidłowy numer gry!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        games[index]["description"] = opis
        save_games()
        print(f"Added description to '{stara_nazwa['name']}' game.")

        embed = discord.Embed(
            title="Dodano opis",
            description=(
                f"Gra: **{games[index]['name']}**\n"
                f"Opis: {opis}"
            ),
            color=discord.Color.blue()
        )
        await message.channel.send(embed=embed)

    if message.content.startswith("!usungre "):
        parts = message.content.split(" ", 1)
        if len(parts) < 2:
            embed = discord.Embed(
                title="Błąd",
                description="Użycie: `!usungre [numer gry z listy]`",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        index_str = parts[1].strip()
        if not index_str.isdigit():
            embed = discord.Embed(
                title="Błąd",
                description="Numer gry musi być liczbą!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        index = int(index_str) - 1
        if index < 0 or index >= len(games):
            embed = discord.Embed(
                title="Błąd",
                description="Nieprawidłowy numer gry!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        removed_game = games.pop(index)
        save_games()
        print(f"Removed '{removed_game['name']}' from games to play list.")

        embed = discord.Embed(
            title="Usunięto grę",
            description=f"Z listy usunięto: **{removed_game['name']}**",
            color=discord.Color.orange()
        )
        await message.channel.send(embed=embed)

    if message.content.startswith("!edytujopis "):
        parts = message.content.split(" ", 2)
        if len(parts) < 3:
            embed = discord.Embed(
                title="Błąd",
                description="Użycie: `!edytujopis [numer gry z listy] [nowy opis]`",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        index_str = parts[1].strip()
        nowy_opis = parts[2].strip()

        if not index_str.isdigit():
            embed = discord.Embed(
                title="Błąd",
                description="Numer gry musi być liczbą!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        index = int(index_str) - 1
        if index < 0 or index >= len(games):
            embed = discord.Embed(
                title="Błąd",
                description="Nieprawidłowy numer gry!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        stara_nazwa = games[index]["name"]
        games[index]["description"] = nowy_opis
        save_games()
        print(f"Edited description of '{stara_nazwa['name']}' game.")

        embed = discord.Embed(
            title="Edytowano opis gry",
            description=(
                f"Gra: **{stara_nazwa}**\n"
                f"Nowy opis: {nowy_opis}"
            ),
            color=discord.Color.blue()
        )
        await message.channel.send(embed=embed)

    if message.content.startswith("!gry"):
        if not games:
            embed = discord.Embed(
                title="Lista gier",
                description="Brak gier na liście.",
                color=discord.Color.blue()
            )
            await message.channel.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Lista gier",
                description="Poniżej znajduje się lista gier, w które chcemy zagrać:",
                color=discord.Color.blue()
            )
            for i, g in enumerate(games, start=1):
                name = g["name"]
                desc = g["description"] if g["description"] else "Brak opisu"
                embed.add_field(
                    name=f"{i}. {name}",
                    value=desc,
                    inline=False
                )
            await message.channel.send(embed=embed)

    if message.content.startswith("!ile"):
        ref_date = load_reference_date()
        today = date.today()
        diff = (today - ref_date).days  # może być też ujemne, jeżeli ref_date jest w przyszłości

        # Budujemy ładny embed z wynikiem
        embed = discord.Embed(
            title="Ile dni minęło od ostatniego serwera minecraft?",
            color=discord.Color.blue()
        )

        # Jeżeli diff < 0, to data bazowa jest w przyszłości
        if diff < 0:
            embed.add_field(
                name="Wynik",
                value=(
                    f"Ustawiona data ({ref_date}) jest w przyszłości!\n"
                    f"Do **{ref_date}** pozostało jeszcze **{abs(diff)}** dni."
                ),
                inline=False
            )
        else:
            embed.add_field(
                name=f"*{diff} dni*... 😢",
                value=(
                    f""
                ),
                inline=False
            )
            embed.set_image(url="https://media.discordapp.net/attachments/607581853880418366/1302050384184999978/image.png?ex=67c6e2aa&is=67c5912a&hm=a8b52b3437f22136b0436de0c4da302ed0ef8800f64757598c0fd0da3cd639c0&=&format=webp&quality=lossless&width=1437&height=772")

        await message.channel.send(embed=embed)

    # Komenda !ilereset
    if message.content.startswith("!ilereset"):
        # Resetujemy datę do dzisiejszego dnia
        now = date.today()
        save_reference_date(now)
        print("Reseted reference day.")

        # Tworzymy embed z komunikatem o resecie
        embed = discord.Embed(
            title="Zresetowano odliczanie",
            description=(
                f"Od teraz liczba dni będzie naliczana od dzisiejszej daty:\n"
                f"**{now.isoformat()}**"
            ),
            color=discord.Color.orange()
        )
        await message.channel.send(embed=embed)


# Uruchomienie bota
client.run(DISCORD_TOKEN)
