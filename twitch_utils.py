import requests


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


TWITCH_CLIENT_ID = load_token('txt/twitch_client_id.txt')
TWITCH_CLIENT_SECRET = load_token('txt/twitch_client_secret.txt')


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
