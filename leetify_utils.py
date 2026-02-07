import requests
import os
import discord
from discord import app_commands
import re
import json
from datetime import datetime
import asyncio

GUILD_ID = 551503797067710504

LEETIFY_API_FILE = "txt/leetify_api.txt"

def load_token(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding="utf-8") as file:
                print(f"{LEETIFY_API_FILE} loaded.")
                return file.read().strip()
        else:
            print(f"File {filename} not found.")
            return None
    except Exception as e:
        print(f"Error loading token from {filename}: {e}")
        return None

LEETIFY_API_KEY = load_token(LEETIFY_API_FILE)
STATS_CACHE_FILE = "txt/leetify_stats_cache.json"

# Słownik graczy (Nick: Steam64ID)
PLAYERS_MAP = {
    "utopiasz": "76561198408446680",
    "-Masny-": "76561198255128029",
    "Kajetov": "76561198199844774",
    "MlodyHubii": "76561198327010547",
    "radzioswir": "76561198424847627",
    "PhesterM9": "76561199109845311",
    "-mateuko": "76561198284074094",
    "Kvzia": "76561198111418150",
    "BEJLI": "76561198311171407"
}

def load_stats_cache():
    if os.path.exists(STATS_CACHE_FILE):
        try:
            with open(STATS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"date": "", "data": {}}

def save_stats_cache(cache_data):
    try:
        with open(STATS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"[Leetify] Error saving cache: {e}")

async def ensure_cache_updated():
    cache = load_stats_cache()
    today = datetime.now().strftime("%Y-%m-%d")

    # Jeśli data w cache jest inna niż dzisiejsza, robimy update wszystkich graczy
    if cache.get("date") != today:
        print("[Leetify] Cache outdated. Updating all players...")
        new_data = {}
        
        # Uruchamiamy w wątku, żeby nie blokować bota
        def fetch_all():
            temp_data = {}
            for nick, sid in PLAYERS_MAP.items():
                print(f"[Leetify] Background update: {nick}")
                p_data = get_leetify_profile(sid)
                if p_data:
                    temp_data[sid] = p_data
            return temp_data

        fetched_data = await asyncio.to_thread(fetch_all)
        
        cache = {
            "date": today,
            "data": fetched_data
        }
        save_stats_cache(cache)
        print("[Leetify] Cache updated successfully.")
    
    return cache

def get_rank_emoji(current_val, stat_key, steam_id, cache_data):
    """
    Oblicza rangę gracza na tle innych z PLAYERS_MAP.
    Zwraca emoji: 🥇, 🥈, 🥉, lub 💩 (ostatni), lub pusty string.
    
    stat_key: nazwa klucza w strukturze JSON (np. 'aim', 'reaction_time_ms')
    lower_is_better: True dla czasu reakcji i preaim.
    """
    
    # Statystyki, gdzie niższy wynik = lepiej
    LOWER_IS_BETTER = ["reaction_time_ms", "preaim"]
    
    # Zbieramy wyniki wszystkich graczy z cache (plus aktualny gracz, jeśli ma świeższy wynik poza cachem)
    # Lista par (steam_id, value)
    scores = []
    
    # Dodajemy dane z cache
    players_data = cache_data.get("data", {})
    
    # Musimy znaleźć lokalizację statystyki w JSONIE Leetify
    # Struktura jest płaska w cache? Nie, cache trzyma całe JSONy profili.
    
    def extract_val(p_json, s_key):
        # Sprawdzamy rating (główny obiekt)
        if "rating" in p_json and s_key in p_json["rating"]:
            return p_json["rating"][s_key]
        # Sprawdzamy stats (obiekt stats)
        if "stats" in p_json and s_key in p_json["stats"]:
            return p_json["stats"][s_key]
        return None

    for pid, p_json in players_data.items():
        val = extract_val(p_json, stat_key)
        if val is not None:
            scores.append( (pid, float(val)) )

    # Sprawdzamy czy nasz gracz jest w scores, jeśli nie (bo np. fail cache), to trudno - nie porównamy
    # Ale zakładamy że ensure_cache_updated zadziałało.
    # Jeśli scores jest puste, brak emoji
    if len(scores) < 2:
        return ""

    # Sortowanie
    config_lower = stat_key in LOWER_IS_BETTER
    # Jeśli lower is better: sortujemy rosnąco (najmniejszy pierwszy)
    # Jeśli higher is better: sortujemy malejąco (największy pierwszy)
    scores.sort(key=lambda x: x[1], reverse=not config_lower)

    # Znajdź pozycję aktualnego steam_id
    try:
        rank_idx = next(i for i, (pid, v) in enumerate(scores) if pid == steam_id)
        rank = rank_idx + 1 # 1-based
        total = len(scores)

        if rank == 1: return " 🥇"
        if rank == 2: return " 🥈"
        if rank == 3: return " 🥉"
        if rank == total: return " 💩"
    except StopIteration:
        pass
        
    return ""

def get_leetify_profile(steam64_id):
    if not LEETIFY_API_KEY:
        print("Leetify API key is missing.")
        return None

    url = "https://api-public.cs-prod.leetify.com/v3/profile"
    headers = {
        "Authorization": f"Bearer {LEETIFY_API_KEY}"
    }
    params = {
        "steam64_id": steam64_id
    }

    try:
        print(f"[DEBUG] Leetify Request for {steam64_id}")
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"[DEBUG] 404 Not Found for {steam64_id}. Response: {response.text}")
            return None
        else:
            print(f"[DEBUG] API Error {response.status_code} for {steam64_id}. Response: {response.text}")
            return None
    except Exception as e:
        print(f"[DEBUG] Exception for {steam64_id}: {e}")
        return None

def get_steam_avatar(steam64_id):
    """Pobiera avatar ze Steam Community (XML) bez klucza API."""
    url = f"https://steamcommunity.com/profiles/{steam64_id}?xml=1"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            # Prosty regex do wyciągnięcia avatarFull z sekcji CDATA
            # Content: <avatarFull> <![CDATA[ https://... ]]> </avatarFull>
            match = re.search(r"<avatarFull>\s*<!\[CDATA\[(.*?)]]>", resp.text, re.DOTALL)
            if match:
                return match.group(1).strip()
    except Exception as e:
        print(f"[DEBUG] Failed to fetch steam avatar: {e}")
    return None

async def setup_leetify_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    # Autocomplete callback for SteamID (based on nicknames)
    async def leetify_player_autocomplete(interaction: discord.Interaction, current: str):
        query = current.lower()
        choices = []
        for name, sid in PLAYERS_MAP.items():
            if query in name.lower():
                choices.append(app_commands.Choice(name=name, value=sid))
        # Add option to allow direct steamid input if needed, but primarily use dictionary
        # If input looks like steamid (digits > 10 chars), maybe add it as a choice?
        # But user requested "like faceit" so nickname selection returning ID is key.
        return choices[:25]

    @tree.command(
        name="leetify",
        description="Pobiera profil gracza z Leetify (wybierz nick lub wpisz Steam64 ID)",
        guild=guild
    )
    @app_commands.describe(steam_id="Nick z listy lub Steam64 ID gracza")
    @app_commands.autocomplete(steam_id=leetify_player_autocomplete)
    async def leetify(interaction: discord.Interaction, steam_id: str):
        await interaction.response.defer()
        
        # 1. Pobierz/Aktualizuj cache tła (wszyscy gracze)
        cache = await ensure_cache_updated()
        
        # 2. Pobierz aktualne dane wywoływanego gracza (świeże)
        data = get_leetify_profile(steam_id)
        
        if not data:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Błąd",
                    description=f"Nie znaleziono profilu Leetify dla ID: `{steam_id}` lub profil jest prywatny.",
                    color=discord.Color.red()
                )
            )
            return

        # Aktualizuj tego konkretnego gracza w cache "w locie", żeby ranking był live dla niego
        if "data" not in cache: cache["data"] = {}
        cache["data"][steam_id] = data
        # Opcjonalnie zapisz: save_stats_cache(cache) - nie trzeba, bo cache główny jest raz dziennie, 
        # ale update w pamięci pozwala obliczyć poprawny ranking dla TEGO zapytania.

        # Przetwarzanie danych zgodnie z nowym formatem API
        username = data.get("name", "Nieznany")
        
        # Wyciąganie awatara - próba pobrania ze Steam
        avatar_url = get_steam_avatar(steam_id)
        if not avatar_url:
             # Fallback: leetify meta (też często puste, ale warto sprawdzić)
             avatar_url = data.get("meta", {}).get("avatarUrl", "")

        # Rangi
        ranks = data.get("ranks", {})
        leetify_rank = ranks.get("leetify", "N/A")
        premier_rank = ranks.get("premier", "N/A")
        faceit_lvl = ranks.get("faceit", "N/A")
        
        skill_level_txt = f"Premier: {premier_rank}\n | Faceit: {faceit_lvl}"

        # Tworzenie embeda
        embed = discord.Embed(
            title=f"Profil Leetify: {username}",
            description=f"Leetify Rating: {leetify_rank}\n{skill_level_txt}",
            url=f"https://leetify.com/public/profile/{steam_id}",
            color=discord.Color.teal()
        )
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        # Rating (Aim, Positioning, Utility, Clutch)
        rating = data.get("rating", {})
        if rating:
            aim = rating.get("aim", 0)
            e_aim = get_rank_emoji(aim, "aim", steam_id, cache)
            
            positioning = rating.get("positioning", 0)
            e_pos = get_rank_emoji(positioning, "positioning", steam_id, cache)
            
            utility = rating.get("utility", 0)
            e_util = get_rank_emoji(utility, "utility", steam_id, cache)
            
            clutch = rating.get("clutch", 0)
            e_clutch = get_rank_emoji(clutch, "clutch", steam_id, cache)
            
            embed.add_field(name=f"Aim{e_aim}", value=f"{aim:.1f}", inline=True)
            embed.add_field(name=f"Positioning{e_pos}", value=f"{positioning:.1f}", inline=True)
            embed.add_field(name=f"Utility{e_util}", value=f"{utility:.1f}", inline=True)
            embed.add_field(name=f"Clutch{e_clutch}", value=f"{clutch:.2f}", inline=True)

        # Dodatkowe statystyki
        stats = data.get("stats", {})
        if stats:
            reaction = stats.get("reaction_time_ms", 0)
            e_reac = get_rank_emoji(reaction, "reaction_time_ms", steam_id, cache)
            
            spray = stats.get("spray_accuracy", 0)
            e_spray = get_rank_emoji(spray, "spray_accuracy", steam_id, cache)
            
            preaim = stats.get("preaim", 0)
            e_preaim = get_rank_emoji(preaim, "preaim", steam_id, cache)
            
            traded_deaths = stats.get("traded_deaths_success_percentage", 0)
            e_trade = get_rank_emoji(traded_deaths, "traded_deaths_success_percentage", steam_id, cache)

            embed.add_field(name=f"Reakcja{e_reac}", value=f"{reaction:.0f} ms", inline=True)
            embed.add_field(name=f"Spray Acc{e_spray}", value=f"{spray:.1f}%", inline=True)
            embed.add_field(name=f"Preaim{e_preaim}", value=f"{preaim:.1f}°", inline=True)
            embed.add_field(name=f"Traded Death{e_trade}", value=f"{traded_deaths:.1f}%", inline=True)
            embed.add_field(name="\n", value="\u200b", inline=True)  # pusty dla layoutu

        # Ostatni mecz
        recent_matches = data.get("recent_matches", [])
        if recent_matches:
            last_match = recent_matches[0]
            
            map_name = last_match.get("map_name", "Unknown").replace("de_", "")
            outcome = last_match.get("outcome", "unknown")
            outcome_icon = "✅" if outcome == "win" else "❌" if outcome == "loss" else "❓"
            
            score_data = last_match.get("score", [])
            score_str = f"{score_data[0]}:{score_data[1]}" if len(score_data) >= 2 else "?:?"
            
            lm_preaim = last_match.get("preaim", 0)
            lm_reaction = last_match.get("reaction_time_ms", 0)
            lm_acc_spot = last_match.get("accuracy_enemy_spotted", 0)
            lm_acc_head = last_match.get("accuracy_head", 0)
            lm_spray = last_match.get("spray_accuracy", 0)

            embed.add_field(
                name=f"Ostatni mecz: {map_name} {outcome_icon} | **{score_str}**",
                value="\u200b",
                inline=False
            )
            
            embed.add_field(name="Preaim", value=f"{lm_preaim:.1f}°", inline=True)
            embed.add_field(name="Reaction", value=f"{lm_reaction:.0f} ms", inline=True)
            embed.add_field(name="Spot Acc", value=f"{lm_acc_spot:.1f}%", inline=True)
            embed.add_field(name="HS Acc", value=f"{lm_acc_head:.1f}%", inline=True)
            embed.add_field(name="Spray", value=f"{lm_spray:.1f}%", inline=True)

        embed.set_footer(text="Dane z Leetify API")
        print(f"[Leetify] Fetched profile for {steam_id} ({username})")
        await interaction.followup.send(embed=embed)
