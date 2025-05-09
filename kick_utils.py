import requests


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


def get_kick_stream_data(username):
    """
    Funkcja sprawdza, czy kanał o danym username (slug) jest aktualnie live.
    Zwraca słownik {live: bool, title: str, thumbnail_url: str lub None}.
    Jeśli API Kick różni się polami, należy je dopasować.
    """

    # Ustalony endpoint Kick (przykład):
    url = f"https://api.kichat.dev/api/v2/channels/{username}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            livestream = data["livestream"]
            is_live = livestream["is_live"]
            title = livestream["session_title"]
            thumbnail = livestream["thumbnail"]["url"]  # lub data.get('thumbnail_urls', {}).get('default')

            print(f"[DEBUG] is_live={is_live}, title={title}, thumbnail={thumbnail}")

            return {
                'live': is_live,
                'title': title,
                'thumbnail_url': thumbnail
            }
        else:
            print(f"[DEBUG] Błąd API Kick: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"[DEBUG] Wyjątek w trakcie zapytania do Kick API: {e}")
        return None

