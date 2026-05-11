import requests
from startup_logger import record_startup_step


def load_token(filename, startup_label=None):
    try:
        with open(filename, 'r') as file:
            token = file.read().strip()
            if startup_label:
                record_startup_step(startup_label, True, filename)
            return token
    except FileNotFoundError:
        if startup_label:
            record_startup_step(startup_label, False, f"{filename} not found")
        else:
            print(f"File not found: {filename}. Make sure the file exists.")
        return None
    except Exception as e:
        if startup_label:
            record_startup_step(startup_label, False, f"{filename}: {e}")
        else:
            print(f"Error loading token from {filename}: {e}")
        return None


TWITCH_CLIENT_ID = load_token('txt/twitch_client_id.txt', startup_label="Twitch client ID")
TWITCH_CLIENT_SECRET = load_token('txt/twitch_client_secret.txt', startup_label="Twitch client secret")


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
            viewer_count = stream.get('viewer_count', 0)
            return {
                'live': True,
                'thumbnail_url': thumbnail_url,
                'title': stream['title'],
                'viewer_count': viewer_count
            }
        else:  # Stream offline
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
