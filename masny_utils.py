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

    # Formatowanie odpowiedzi
    # last_match_stats = f'**Ostatni mecz gracza {player_nickname}:**\n'
    last_match_stats = f'**Mapa**: {map_name}\n'
    last_match_stats += f'**Wynik**: {result}\n'
    last_match_stats += f'**K/D/A**: {kills}/{deaths}/{assists}\n'
    last_match_stats += f'**HS%**: {hs}%\n'

    return last_match_stats


def resetmasny():
    global masny_counter
    masny_counter = {key: 0 for key in masny_counter}  # Resetujemy licznik
    save_masny_data()  # Zapisujemy zerowane statystyki do pliku
    load_masny_data()
