import requests
import json


def load_token(filename):
    try:
        with open(filename, 'r') as file:
            print(f"{filename} loaded.")
            return file.read().strip()
    except FileNotFoundError:
        print(f"Plik {filename} nie został znaleziony. Upewnij się, że plik istnieje.")
        return None
    except Exception as e:
        print(f"Wystąpił błąd podczas wczytywania tokena z pliku {filename}: {e}")
        return None


KICK_CLIENT_ID = load_token('txt/kick_client_id.txt')
KICK_SECRET_ID = load_token('txt/kick_client_secret.txt')


def get_kick_access_token():
    """
    Przykładowa funkcja uzyskująca token OAuth dla Kick,
    zakładając, że platforma ma podobny endpoint do /oauth2/token
    przy client_credentials.
    """
    url = 'https://api.kick.com/oauth2/token'  # UWAGA: Ścieżka do potwierdzenia w dokumentacji Kick
    params = {
        'client_id': KICK_CLIENT_ID,
        'client_secret': KICK_SECRET_ID,
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(url, data=params)  # lub json=params, zależnie od wymagań
        if response.status_code == 200:
            token = response.json().get('access_token')
            return token
        else:
            print(f"[DEBUG] Błąd podczas uzyskiwania tokena Kick: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"[DEBUG] Wyjątek w trakcie uzyskiwania tokena: {e}")
        return None


import requests

def get_kick_stream_data(username):
    """
    Funkcja sprawdza, czy kanał o danym username (slug) jest aktualnie live.
    Zwraca słownik z informacjami o transmisji.
    """

    url = f"https://api.kichat.dev/api/v2/channels/{username}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            livestream = data.get("livestream")

            if not livestream:
                print("[DEBUG] Brak aktywnej transmisji.")
                return {
                    'live': False,
                    'title': None,
                    'thumbnail_url': None,
                    'viewer_count': None,
                    'viewers': None
                }

            is_live = livestream.get("is_live", False)
            title = livestream.get("session_title", "Brak tytułu")
            thumbnail = livestream.get("thumbnail", {}).get("url")
            viewer_count = livestream.get("viewer_count", None)

            # liczba wyświetleń kategorii (np. IRL): pierwsza kategoria
            categories = livestream.get("categories", [])
            viewers = categories[0].get("viewers") if categories else None

            # print(f"[DEBUG] is_live={is_live}")
            # print(f"[DEBUG] title={title}")
            # print(f"[DEBUG] thumbnail_url={thumbnail}")
            # print(f"[DEBUG] viewer_count={viewer_count}")
            # print(f"[DEBUG] viewers (z kategorii)={viewers}")

            return {
                'live': is_live,
                'title': title,
                'thumbnail_url': thumbnail,
                'viewer_count': viewer_count,
                'viewers': viewers
            }

        else:
            print(f"[DEBUG] Błąd API Kick: {response.status_code}, {response.text}")
            return None

    except Exception as e:
        print(f"[DEBUG] Wyjątek w trakcie zapytania do Kick API: {e}")
        return None


