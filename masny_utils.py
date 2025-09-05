import requests
import os
from faceit_utils import *

# Plik do przechowywania danych
MASNY_FILE = "txt/masny.txt"

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
        print("Unable to read masny.txt - creating a new one.")
        save_masny_data()  # Inicjalizacja pliku z zerowymi wartościami

    # Wczytywanie danych z pliku i walidacja formatu danych
    with open(MASNY_FILE, "r") as file:
        for line in file:
            try:
                key, count = line.strip().split()
                if key in masny_counter:  # Sprawdzanie, czy klucz jest prawidłowy
                    masny_counter[key] = int(count)
            except ValueError:
                print(f"Error in reading line: {line}")
        print("Masny.txt loaded.")


# Wczytanie danych przy starcie bota
load_masny_data()

# Inicjalizacja listy wymówek
wymowki = [
]

# Dodajemy funkcję do zapisywania wymówek do pliku
WYMOWKI_FILE = "txt/wymowki.txt"


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
            print("wymowki.txt loaded.")


# Wczytujemy wymówki przy starcie bota
load_wymowki()


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
    adr = float(last_match.get('stats', {}).get('ADR', 0))

    # Formatowanie odpowiedzi
    # last_match_stats = f'**Ostatni mecz gracza {player_nickname}:**\n'
    last_match_stats = f'**Mapa**: {map_name}\n'
    last_match_stats += f'**Wynik**: {result}\n'
    last_match_stats += f'**K/D/A**: {kills}/{deaths}/{assists}\n'
    last_match_stats += f'**HS%**: {hs}%\n'
    last_match_stats += f'**ADR**: {adr}\n'

    return last_match_stats


def resetmasny():
    global masny_counter
    masny_counter = {key: 0 for key in masny_counter}  # Resetujemy licznik
    save_masny_data()  # Zapisujemy zerowane statystyki do pliku
    load_masny_data()

import discord
from discord import app_commands

GUILD_ID = 551503797067710504

# Linki do zdjęć dla miejsc 1-5
image_links = {
    "1": "https://cdn.discordapp.com/attachments/809156611167748176/1330901097816129596/BE8227A4-FD7F-42E4-A48F-350CD124D92B.png?ex=678fa9bc&is=678e583c&hm=ac937a4d34a9375cc56fefdbb1d228733a3fdf0daaaa720e5a020ecd302a878e&",
    "2": "https://cdn.discordapp.com/attachments/809156611167748176/1330905145772474428/61A0B076-BD51-400C-AF19-A7B1D626B1B1.png?ex=678fad81&is=678e5c01&hm=6f06532e17ca3e49d550adc2cf84ff19f80b91e5b7b8833c7c7dc54061f40882&",
    "3": "https://cdn.discordapp.com/attachments/809156611167748176/1330911802049036340/2698389E-237A-4840-8A63-07F996640858.png?ex=678fb3b4&is=678e6234&hm=4870f7636f0053600f02e59e2c9332c5c0272d04e8cb25d25ad643c6f2947739&",
    "4": "https://media.discordapp.net/attachments/778302928338550865/1300471813146415176/B4B5C4D4-8E00-43CE-927B-E9CC47FB2201.png?ex=678fb441&is=678e62c1&hm=661a9436fdf6bbe526df0afa62a28adf1ae8a4dbca4dab0f333d4a4c059d9a0d&=&format=webp&quality=lossless&width=359&height=601",
    "5": "https://cdn.discordapp.com/attachments/809156611167748176/1330906894302318592/pobrane_1.gif?ex=678faf22&is=678e5da2&hm=908f4934957c128b1531edc28da1820b096fd8a1bd35358621e794336969884e&"
}

async def setup_masny_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
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
        load_masny_data()  # Załaduj aktualny stan z pliku
        global masny_counter

        # Dodawanie miejsca
        if miejsce and miejsce in masny_counter:
            masny_counter[miejsce] += 1
            save_masny_data()
            last_match_stats = await display_last_match_stats()
            image_url = image_links.get(miejsce)
            embed = discord.Embed(
                title=f"🏆 Masny zajął {miejsce} miejsce!",
                color=discord.Color.gold()
            )
            if image_url:
                embed.set_image(url=image_url)
            embed.add_field(name="📊 Statystyki ostatniego meczu", value=last_match_stats, inline=False)
            await interaction.response.send_message(embed=embed)
            return

        # Odejmowanie miejsca
        if miejsce and miejsce.startswith('-') and miejsce[1:] in masny_counter:
            place = miejsce[1:]
            if masny_counter[place] > 0:
                masny_counter[place] -= 1
                save_masny_data()
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

        # Wyświetlanie statystyk
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

    @tree.command(
        name="resetmasny",
        description="Resetuje statystyki miejsc Masnego",
        guild=guild
    )
    async def resetmasny_slash(interaction: discord.Interaction):
        resetmasny()
        await interaction.response.send_message("✅ Statystyki w masny.txt zostały zresetowane!")

    @tree.command(
        name="spawn",
        description="Wołaj Masnego na CSa, opcjonalnie z podaniem godziny",
        guild=guild
    )
    @app_commands.describe(
        godzina="Opcjonalna godzina, np. 16 lub 16:00"
    )
    async def spawn(interaction: discord.Interaction, godzina: str = None):
        if godzina:
            # Uproszczona walidacja formatu godziny
            if ":" in godzina:
                try:
                    hour, minute = godzina.split(":")
                    hour = int(hour)
                    minute = int(minute)
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        formatted_time = f"{hour:02d}:{minute:02d}"
                    else:
                        await interaction.response.send_message("⚠️ Nieprawidłowy format godziny! Użyj formatu 0-23:0-59.")
                        return
                except ValueError:
                    await interaction.response.send_message("⚠️ Nieprawidłowy format godziny! Użyj formatu 16:00.")
                    return
            else:
                # Format typu 16
                try:
                    hour = int(godzina)
                    if 0 <= hour <= 23:
                        formatted_time = f"{hour:02d}:00"
                    else:
                        await interaction.response.send_message("⚠️ Nieprawidłowa godzina! Podaj liczbę od 0 do 23.")
                        return
                except ValueError:
                    await interaction.response.send_message("⚠️ Nieprawidłowy format godziny! Podaj liczbę od 0 do 23.")
                    return
                    
            embed = discord.Embed(
                title="🗣️ Eee misia!",
                description=f"<@606785554918539275>, wołają cię na CSa na godzinę **{formatted_time}**!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="🗣️ Eee misia!",
                description="<@606785554918539275>, wołają cię na CSa!",
                color=discord.Color.green()
            )
            
        embed.set_footer(text="Spawn Masnego aktywowany!")
        await interaction.response.send_message(embed=embed)

