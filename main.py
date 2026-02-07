import random
from datetime import date

import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
import re
from discord.ext import commands, tasks
import json
import asyncio
import datetime
from datetime import datetime, timedelta
import sys
import threading

from twitch_utils import *
from masny_utils import *
from faceit_utils import *
from kick_utils import *
from commands import games as games_module
from commands import help as help_module
from commands import excuses as excuses_module
from commands import instants
from commands import challenges as challenges_module
from commands import twitch_kick
from commands import mod as mod_module
from commands import minecraft
import faceit_utils
import masny_utils
from commands import football
import leetify_utils


games_data = games_module.load_games()  # commands/games.py


# from soundcloud_utils import *


# TODO:
#   dodać wynik meczu przy !last (tzn. np 13:10)
#   pobawić się z api spotify
#   !premier - raczej ciezkie do zrobienia
#   sprawdzanie cen skrzynek z csa


# Funkcja do wczytania tokena z pliku
def load_token(filename):
    try:
        with open(filename, 'r') as file:
            print(f'{filename} loaded.')
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
intents.members = True
intents.presences = True
client = commands.Bot(command_prefix="!", intents=intents)

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
        print("reaction_state.json loaded.")
    except FileNotFoundError:
        reaction_active = False
        print("Error in reading reaction_state.json.")

BETS_FILE = "txt/bets.json"
def load_bets():
    try:
        with open(BETS_FILE, "r") as file:
            print(f"{BETS_FILE} loaded.")
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Error in loading {BETS_FILE}. FileNotFoundError")
        return {}

def save_bets(bets):
    with open(BETS_FILE, "w") as file:
        json.dump(bets, file, indent=4)

STATS_FILE = "txt/user_stats.json"
STATS_HISTORY_FILE = "txt/user_stats_history.json"
def load_json(file_path):
    try:
        with open(file_path, "r") as file:
            print(f"{file_path} loaded.")
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Error in loading {file_path}. FileNotFoundError")
        return {}

def save_json(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


TARGET_USER_NAME = "phester102"
user_connection_count = 0
user_stats = load_json(STATS_FILE)
user_stats_history = load_json(STATS_HISTORY_FILE)
current_date = datetime.now().strftime("%Y-%m-%d")
user_stats.setdefault(current_date, 0)
user_stats_history.setdefault(current_date, 0)
save_json(user_stats, STATS_FILE)
save_json(user_stats_history, STATS_HISTORY_FILE)


async def reset_connection_count():
    global user_stats, user_stats_history

    while True:
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = (midnight - now).total_seconds()
        await asyncio.sleep(seconds_until_midnight)

        current_date = datetime.now().strftime("%Y-%m-%d")
        previous_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        user_stats[current_date] = 0
        user_stats_history.setdefault(current_date, 0)
        save_json(user_stats, STATS_FILE)
        save_json(user_stats_history, STATS_HISTORY_FILE)
        print("Statystyki zresetowane!")

        channel = client.get_channel(1346496307023581274)

        # Podsumowanie betów za wczoraj
        bets = load_bets()
        previous_day_bets = bets.get(previous_date, {})
        actual_logins = user_stats_history.get(previous_date, 0)

        if previous_day_bets and channel:
            embed = discord.Embed(
                title="🎲 Wyniki zakładów za wczoraj!",
                description=f"Użytkownik **{TARGET_USER_NAME}** zalogował się **{actual_logins}** razy w dniu {previous_date}.",
                color=discord.Color.purple()
            )

            bets_history = bets.get("bets", {})
            closest_users = []  # Lista użytkowników z najbliższą różnicą
            closest_difference = float('inf')  # Najmniejsza różnica
            exact_match = False  # Flaga, aby wiedzieć, czy był dokładny traf
            user_points = {}  # Słownik do przechowywania punktów użytkowników

            # Zliczanie punktów na podstawie zakładów
            for user_id, data in previous_day_bets.items():
                difference = abs(actual_logins - data["guess"])
                if difference == 0:
                    result = 5  # Dokładne trafienie
                    exact_match = True
                elif difference < closest_difference:
                    result = 3  # Najbliższe trafienie
                    closest_users = [user_id]  # Zresetuj listę najbliższych użytkowników
                    closest_difference = difference
                elif difference == closest_difference:
                    result = 3  # Dla użytkownika o tej samej różnicy
                    closest_users.append(user_id)

                # Dodanie wyniku do historii zakładu
                record = {
                    "date": previous_date,
                    "value": data["guess"],
                    "actual": actual_logins,
                    "result": result
                }
                bets_history.setdefault(user_id, []).append(record)

                # Zapisanie punktów użytkownika
                user_points[user_id] = user_points.get(user_id, 0) + result

            # Jeżeli nikt nie trafił dokładnie, przyznaj punkty dla najbliższych
            if not exact_match and closest_users:
                for user_id in previous_day_bets:
                    if user_id in closest_users:
                        bets_history[user_id][-1]["result"] = 3  # Najbliżsi dostają 3 punkty
                    else:
                        bets_history[user_id][-1]["result"] = -1  # Reszta dostaje -1

            bets["bets"] = bets_history

            embed.set_footer(text="Nowe zakłady na dzisiaj są już otwarte! 🔓")
            await channel.send(embed=embed)

            # Wyświetlenie punktów dla każdego użytkownika
            points_message = "📝 Podsumowanie punktów za wczoraj:\n"
            for user_id, points in user_points.items():
                user = discord.utils.get(client.users, id=user_id)
                username = user.name if user else f"Użytkownik {user_id}"  # Sprawdzamy czy użytkownik istnieje
                points_message += f"{username}: **{points} punktów**\n"

            # Wyświetlanie punktów w kanale
            await channel.send(points_message)

        # Zapowiedź na dzień następny
        today_bets = bets.get(current_date, {})
        if today_bets and channel:
            preview = discord.Embed(
                title=f"📢 Zakłady na {current_date} (dalsze obstawienia)",
                description=f"Liczba użytkowników, którzy obstawili: **{len(today_bets)}**",
                color=discord.Color.orange()
            )
            for user_id, data in today_bets.items():
                preview.add_field(
                    name=data["name"],
                    value=f"Obstawiono: **{data['guess']}** połączeń",
                    inline=False
                )
            await channel.send(embed=preview)

        save_bets(bets)


def polaczenie_label(count: int) -> str:
    if count == 1:
        return "połączenie"
    elif 2 <= count <= 4:
        return "połączenia"
    else:
        return "połączeń"

GUILD_ID = 551503797067710504

# Start a background listener that shuts down the bot when 'stop' is typed in the console

def start_console_listener():
    def _listen():
        try:
            for line in sys.stdin:
                if line.strip().lower() == "stop":
                    print("Console command 'stop' received. Shutting down bot...")
                    try:
                        fut = asyncio.run_coroutine_threadsafe(client.close(), client.loop)
                        fut.result(timeout=10)
                    except Exception as e:
                        print(f"Error during shutdown: {e}")
                    os._exit(0)
        except Exception as e:
            print(f"Console listener error: {e}")
    t = threading.Thread(target=_listen, daemon=True)
    t.start()

# Obsługa zdarzenia - gdy bot jest gotowy
@client.event
async def on_ready():
    # send_daily_stats(client)
    load_reaction_state()

    await games_module.setup_games_commands(client, client.tree)
    await excuses_module.setup_excuses_commands(client, client.tree, guild_id=GUILD_ID)
    await minecraft.setup_minecraft_commands(client, client.tree, guild_id=GUILD_ID)
    await help_module.setup_help_commands(client, client.tree, guild_id=GUILD_ID)
    await instants.setup_instants_commands(client, client.tree, guild_id=GUILD_ID)
    await twitch_kick.setup_twitch_kick_commands(client, client.tree, guild_id=551503797067710504)
    await challenges_module.setup_challenges_commands(client, client.tree, guild_id=GUILD_ID)
    await mod_module.setup_mod_commands(client, client.tree, guild_id=GUILD_ID)
    await faceit_utils.setup_faceit_commands(client, client.tree, guild_id=GUILD_ID)
    await masny_utils.setup_masny_commands(client, client.tree, guild_id=GUILD_ID)
    await football.setup_football_commands(client, client.tree, guild_id=GUILD_ID)
    await leetify_utils.setup_leetify_commands(client, client.tree, guild_id=GUILD_ID)
    # await youtube_watch.setup_youtube_watch(client, client.tree, guild_id=GUILD_ID)  # start watcher

    print(f'\n{client.user} has connected to Discord!\n\n'
          f'\nOptions:'
          f'\n- Reacting to {reaction_name}: {reaction_active}')
    await client.change_presence(activity=discord.Game(name="/geek - Jestem geekiem"))

    # client.loop.create_task(reset_connection_count())

channel_id = 1346496307023581274  # anty-plaster
# Obsługa wiadomości użytkowników
@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    global user_stats
    if after.name == TARGET_USER_NAME:
        old_status = before.status
        new_status = after.status

        if old_status == discord.Status.offline and new_status != discord.Status.offline:
            current_date = datetime.now().strftime("%Y-%m-%d")
            user_stats[current_date] = user_stats.get(current_date, 0) + 1
            user_stats_history[current_date] = user_stats_history.get(current_date, 0) + 1
            save_json(user_stats, STATS_FILE)
            save_json(user_stats_history, STATS_HISTORY_FILE)

            channel = after.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="ALARM!",
                    description=f"Użytkownik **{after.name}** jest teraz dostępny!\n"
                                f"To **{user_stats[current_date]}. połączenie** dzisiaj!",
                    color=discord.Color.red()
                )
                embed.set_image(url="https://media.discordapp.net/attachments/1346496307023581274/1346496972965679175/"
                                    "2D0BF743-1673-4F01-B648-7FFBD12D6950.png?ex=67c86687&is=67c71507&hm=bf2f675228c76"
                                    "d53ad74fd422679d6cc867073c5bec4698ee75abc09abdc1fad&=&format=webp&quality=lossless")

                print(f"{TARGET_USER_NAME} is online! To {user_stats[current_date]}. połączenie dziś.")
                await channel.send(embed=embed)


# async def start_reset_task():
#     """Rozpoczyna asynchroniczny reset licznika statystyk co 24h."""
#     await reset_connection_count()


@client.event
async def on_message(message):
    global reaction_active
    if message.author == client.user:
        return

    if "https://x.com/" in message.content:
        pattern = r"https://x\.com/[\w\d_]+/status/\d+"
        matches = re.findall(pattern, message.content)

        if matches:
            # Usuń podgląd z oryginalnej wiadomości użytkownika
            try:
                await message.edit(suppress=True)  # Wyłącza wszystkie embedy
            except discord.Forbidden:
                print("Bot nie ma uprawnień do edycji wiadomości!")
            except discord.HTTPException as e:
                print(f"Błąd podczas edycji wiadomości: {e}")

            # Wysyłanie poprawionych linków (bez suppress_embeds, jeśli chcesz, aby bot pokazywał podgląd)
            for link in matches:
                fixed_link = link.replace("x.com", "fixvx.com")
                await message.reply(fixed_link)  # Tu możesz dodać suppress_embeds=False, jeśli chcesz

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

    if message.content.startswith('!guildsync'):
        if message.author.id != 443406275716579348:  # OWNER_ID from mod.py
            await message.channel.send("❌ Nie masz uprawnień do synchronizacji komend.", delete_after=5)
            return
            
        try:
            guild = discord.Object(id=message.guild.id)
            synced = await client.tree.sync(guild=guild)
            await message.channel.send(f"✅ Zsynchronizowano {len(synced)} komend slash dla tego serwera.")
            print(f"Zsynchronizowano {len(synced)} komend dla serwera {message.guild.name}")
        except Exception as e:
            await message.channel.send(f"❌ Błąd synchronizacji: {e}")
            
    if message.content.startswith('!clearcmds'):
        if message.author.id != 443406275716579348:  # OWNER_ID from mod.py
            await message.channel.send("❌ Nie masz uprawnień do tej operacji.", delete_after=5)
            return
            
        try:
            guild = discord.Object(id=message.guild.id)
            client.tree.clear_commands(guild=guild)
            await client.tree.sync(guild=guild)
            await message.channel.send("✅ Wyczyszczono komendy slash dla tego serwera.")
            print(f"Wyczyszczono komendy dla serwera {message.guild.name}")
        except Exception as e:
            await message.channel.send(f"❌ Błąd podczas czyszczenia komend: {e}")

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
                await message.channel.send(f"Klucha wbijaj na csa potrzebujemy cie w naszym składzie {user.mention}")

    if message.content == "!infoplaster" and message.channel.id == 1346496307023581274:
        stats = load_json(STATS_FILE)
        history = load_json(STATS_HISTORY_FILE)

        last_7_days = sorted(stats.items(), key=lambda x: x[0], reverse=True)[:7]
        max_day = max(last_7_days, key=lambda x: x[1])
        nonzero_history = {k: v for k, v in history.items() if v > 0}
        history_max = max(nonzero_history.items(), key=lambda x: x[1]) if nonzero_history else ("Brak", 0)

        dni_tygodnia = {
            "Monday": "Poniedziałek",
            "Tuesday": "Wtorek",
            "Wednesday": "Środa",
            "Thursday": "Czwartek",
            "Friday": "Piątek",
            "Saturday": "Sobota",
            "Sunday": "Niedziela"
        }

        miesiace = {
            "January": "stycznia",
            "February": "lutego",
            "March": "marca",
            "April": "kwietnia",
            "May": "maja",
            "June": "czerwca",
            "July": "lipca",
            "August": "sierpnia",
            "September": "września",
            "October": "października",
            "November": "listopada",
            "December": "grudnia",
        }

        embed = discord.Embed(
            title=f"📊 Statystyki połączeń: {TARGET_USER_NAME}",
            color=discord.Color.green()
        )

        max_value = max(count for _, count in last_7_days)
        bar_max_width = 20  # maksymalna długość paska w znakach

        for day, count in last_7_days:
            date_obj = datetime.strptime(day, "%Y-%m-%d")
            weekday_en = date_obj.strftime("%A")
            month_en = date_obj.strftime("%B")
            weekday_pl = dni_tygodnia.get(weekday_en, weekday_en)
            month_pl = miesiace.get(month_en, month_en)
            day_str = f"{date_obj.day} {month_pl} ({weekday_pl})"

            # Tworzenie paska wykresu ASCII
            bar_length = int((count / max_value) * bar_max_width) if max_value > 0 else 0
            bar = "█" * bar_length + "░" * (bar_max_width - bar_length)

            embed.add_field(
                name=day_str,
                value=f"-> {count} {polaczenie_label(count)}\n{bar}",
                inline=False
            )

        embed.add_field(
            name="📈 Najwięcej połączeń w ostatnim tygodniu",
            value=f"{max_day[0]} – {max_day[1]} razy",
            inline=False,
        )
        embed.add_field(
            name="🏆 Najaktywniejszy dzień w historii *(od 2025-03-13)*",
            value=f"{history_max[0]} – {history_max[1]} razy",
            inline=False,
        )

        # Pobierz obiekt użytkownika
        guild = message.guild
        target_member = discord.utils.get(guild.members, name=TARGET_USER_NAME)

        if target_member and target_member.avatar:
            embed.set_thumbnail(url=target_member.avatar.url)

        await message.channel.send(embed=embed)

    if message.content.startswith("!bet ") and message.channel.id == 1346496307023581274:
        try:
            guess = int(message.content.split(" ")[1])
        except (IndexError, ValueError):
            await message.channel.send("Użycie: `!bet [liczba]`, np. `!bet 10`")
            return

        if guess < 1 or guess > 30:
            await message.channel.send("cmon, bez przesady xD")
            return

        user_id = str(message.author.id)
        user_name = message.author.name

        bet_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        bets_data = load_bets()

        if bet_date in bets_data and user_id in bets_data[bet_date]:
            await message.channel.send(f"Już obstawiłeś zakład na {bet_date}! Poczekaj na kolejną dobę.")
            return

        if bet_date not in bets_data:
            bets_data[bet_date] = {}

        bets_data[bet_date][user_id] = {
            "name": user_name,
            "guess": guess
        }

        save_bets(bets_data)

        await message.channel.send(
            f"🎲 Zapisano zakład: **{user_name}** przewiduje, że **{TARGET_USER_NAME}** zaloguje się **{guess}** razy w dniu **{bet_date}**!"
        )

    if message.content == "!mybets" and message.channel.id == 1346496307023581274:
        bets_data = load_json(BETS_FILE)
        user_bets = bets_data.get("bets", {})
        user_id = str(message.author.id)
        user_history = user_bets.get(user_id, [])

        if not user_history:
            await message.channel.send("Nie obstawiałeś jeszcze żadnych zakładów.")
            return

        embed = discord.Embed(
            title=f"🎯 Historia zakładów: {message.author.name}",
            color=discord.Color.purple()
        )

        for entry in sorted(user_history, key=lambda x: x["date"], reverse=True)[-10:]:
            result_text = "✅ TAK" if entry["result"] else "❌ NIE"
            embed.add_field(
                name=f"{entry['date']}",
                value=f"Typ: **{entry['value']}** | Wynik: {entry['actual']} | {result_text}",
                inline=False
            )

        await message.channel.send(embed=embed)

    if message.content == "!tabela" and message.channel.id == 1346496307023581274:
        bets_data = load_json(BETS_FILE)
        user_bets = bets_data.get("bets", {})
        scores = {}
        exact_hits = {}  # Dla dokładnych trafień

        # Zliczanie punktów i dokładnych trafień
        exact_match = False  # Flaga, żeby wiedzieć, czy był dokładny traf
        closest_users = []  # Lista użytkowników z najbliższą różnicą
        closest_difference = float('inf')  # Inicjalizuj z największą możliwą różnicą

        for user_id, records in user_bets.items():
            total_score = 0
            exact_hits_count = 0

            for record in records:
                if record["value"] == record["actual"]:  # Dokładne trafienie
                    total_score += 5
                    exact_hits_count += 1
                    exact_match = True
                else:
                    difference = abs(record["value"] - record["actual"])

                    if difference < closest_difference:  # Znaleziono nowego najbliższego użytkownika
                        closest_difference = difference
                        closest_users = [user_id]  # Zresetuj listę z najbliższymi użytkownikami
                    elif difference == closest_difference:  # Dodaj użytkownika, jeśli ma równą różnicę
                        closest_users.append(user_id)

                    total_score -= 1  # Błędne obstawienie

            scores[user_id] = total_score
            exact_hits[user_id] = exact_hits_count

        # Logika przyznawania punktów
        if not exact_match and closest_users:
            # Jeżeli nikt nie trafił dokładnie, przyznaj punkty dla najbliższych
            for user_id in user_bets:
                if user_id in closest_users:
                    scores[user_id] = 3  # Najbliżsi dostają 3 punkty
                else:
                    scores[user_id] = -1  # Reszta dostaje -1

        # TOP 5 punktów
        top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        if not top5:
            await message.channel.send("Brak danych do rankingu punktów.")
            return

        embed = discord.Embed(
            title="🥇 TOP 5 punktów",
            description="Dokładne trafienie = +5 pkt \n"
                        "Najbliższe trafienie = +3pkt\n"
                        "Pudło = -1 pkt",
            color=discord.Color.dark_green()
        )

        for user_id, score in top5:
            member = message.guild.get_member(int(user_id))
            name = member.name if member else f"User {user_id}"
            embed.add_field(name=name, value=f"{score} pkt", inline=False)

        # TOP 3 dokładnych trafień
        top3_exact_hits = sorted(exact_hits.items(), key=lambda x: x[1], reverse=True)[:3]
        if top3_exact_hits:
            embed.add_field(
                name="🎯 TOP 3 dokładnych trafień",
                value="",
                inline=False
            )
            for user_id, hits in top3_exact_hits:
                member = message.guild.get_member(int(user_id))
                name = member.name if member else f"User {user_id}"
                embed.add_field(name=name, value=f"{hits} dokładnych trafień", inline=False)

        # Dodanie punktów użytkownika, który użył komendy
        user_id = str(message.author.id)  # ID użytkownika, który wysłał komendę
        user_score = scores.get(user_id, 0)
        user_hits = exact_hits.get(user_id, 0)
        user_name = message.author.name

        embed.add_field(
            name=f"🔹 {user_name} (Ty)",
            value=f"Punkty: {user_score}\nDokładne trafienia: {user_hits}",
            inline=False
        )

        await message.channel.send(embed=embed)

    if message.content == "!bety" and message.channel.id == 1346496307023581274:
        # Pobranie daty na następny dzień oraz dzisiaj
        next_day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        # Ładowanie danych z pliku
        bets_data = load_bets()

        # Bety na następny dzień
        tomorrow_bets = bets_data.get(next_day, {})

        # Bety na dzisiaj (czyli te obstawione wczoraj)
        today_bets = bets_data.get(today, {})

        # Pobranie avatara użytkownika (Geekot #1450)
        target_member = discord.utils.get(message.guild.members, name="Geekot", discriminator="1450")
        avatar_url = target_member.avatar.url if target_member and target_member.avatar else None

        embed = discord.Embed(
            title=f"🎲 Bety na dzień {next_day} oraz {today}",
            description=(
                f"**Bety na jutro:** {len(tomorrow_bets)} użytkowników\n"
                f"**Bety na dziś:** {len(today_bets)} użytkowników"
            ),
            color=discord.Color.purple()
        )

        # Dodajemy avatar użytkownika Geekot
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        # Bety na następny dzień
        if tomorrow_bets:
            embed.add_field(
                name=f"⏩ Bety na {next_day} (jutro)",
                value="\n".join([f"**{data['name']}** \n▪️obstawił **{data['guess']}** logowań" for user_id, data in
                                 tomorrow_bets.items()]),
                inline=False
            )
        else:
            embed.add_field(name=f"⏩ Bety na {next_day} (jutro)", value="Brak obstawień.", inline=False)

        # Bety na dzisiaj
        if today_bets:
            embed.add_field(
                name=f"⏩ Bety na {today} (dziś - obstawione wczoraj)",
                value="\n".join([f"**{data['name']}** \n▪️obstawił **{data['guess']}** logowań" for user_id, data in
                                 today_bets.items()]),
                inline=False
            )
        else:
            embed.add_field(name=f"Bety na {today}", value="Brak obstawień.", inline=False)

        embed.set_footer(
            text="Aby zagłosować, użyj komendy: `!bet [liczba]`, np. `!bet 10`.\nZakład można obstawić tylko raz dziennie."
        )

        # Wysyłanie wiadomości z embedem
        await message.channel.send(embed=embed)

    if message.content == "!gambling" and message.channel.id == 1346496307023581274:
        embed = discord.Embed(
            title="🎲 Zasady zakładów",
            description=(
                "1. Zakłady są obstawiane na **liczbę logowań użytkownika 'phester102'** na Discordzie w ciągu następnej doby.\n"
                "2. Każdy użytkownik może obstawić liczbę logowań.\n"
                "3. Po zakończeniu doby, jeśli ktoś trafi dokładnie liczbę logowań, dostaje **5 punktów**.\n"
                "4. Jeśli ktoś obstawi liczbę logowań, która jest najbliższa, dostaje **3 punkty**.\n"
                "5. Pozostali, którzy się pomylili, dostają **-1 punkt**.\n"
                "6. Każdy użytkownik może obstawić zakład tylko raz dziennie.\n"
                "7. Zakłady na następny dzień otwierają się po zakończeniu podsumowania betów.\n"
                "\nDostępne komendy:\n"
                "`!bet [ilosc]` - obstaw ile razy plaster sie zaloguje\n"
                "`!bety` - pokaż jak głosują dziś użytkownicy\n"
                "`!tabela` - tabela punktów"
            ),
            color=discord.Color.green()
        )
        await message.channel.send(embed=embed)

# Uruchomienie bota
if __name__ == "__main__":
    start_console_listener()
    client.run(DISCORD_TOKEN)
