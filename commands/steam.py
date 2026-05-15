import discord
from discord import app_commands
from discord.ext import tasks
import logging
import aiohttp
import asyncio
import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta

STEAM_HISTORY_FILE = "txt/steam_history.json"
CS2_UPDATES_TRACKING_FILE = "txt/cs2_updates_tracking.json"
CS2_UPDATES_CHANNEL_ID = 1301248598108798996

def load_steam_history():
    if os.path.exists(STEAM_HISTORY_FILE):
        try:
            with open(STEAM_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading steam history: {e}")
    return {}

def save_steam_history(data):
    os.makedirs(os.path.dirname(STEAM_HISTORY_FILE), exist_ok=True)
    try:
        with open(STEAM_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving steam history: {e}")

def load_cs2_updates_tracking():
    """Ładuje dane śledzenia ostatniego commita CS2"""
    if os.path.exists(CS2_UPDATES_TRACKING_FILE):
        try:
            with open(CS2_UPDATES_TRACKING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading CS2 tracking data: {e}")
    return {"last_commit_sha": None}

def save_cs2_updates_tracking(data):
    """Zapisuje dane śledzenia ostatniego commita CS2"""
    os.makedirs(os.path.dirname(CS2_UPDATES_TRACKING_FILE), exist_ok=True)
    try:
        with open(CS2_UPDATES_TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving CS2 tracking data: {e}")

async def fetch_case_history(session: aiohttp.ClientSession, case_name: str):
    """Pobiera stronę HTML skrzynki i wyciąga historię cen"""
    # Kodowanie URL, aby poprawnie odczytać znak spacji i inne np. '&'
    safe_name = urllib.parse.quote(case_name)
    url = f"https://steamcommunity.com/market/listings/730/{safe_name}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                html = await resp.text()
                match = re.search(r'var line1=([^;]+);', html)
                if match:
                    history_data = json.loads(match.group(1))
                    return history_data
    except Exception as e:
        logging.error(f"Error fetching HTML for {case_name}: {e}")
    return None

def process_history(history_list):
    """Przetwarza surową listę ze Steama na konkretne punkty w czasie"""
    if not history_list:
        return None
        
    now = datetime.utcnow()
    parsed_data = []
    
    # Format to zazwyczaj: ["Apr 08 2025 01: +0", 2.741, "235981"]
    for item in history_list:
        try:
            date_str = item[0][:11] # Pobieramy m.in. "Apr 08 2025"
            date_obj = datetime.strptime(date_str, "%b %d %Y")
            price = float(item[1])
            parsed_data.append((date_obj, price))
        except:
            continue
            
    if not parsed_data:
        return None
        
    current_price = parsed_data[-1][1]
    
    def get_price_at_offset(days_offset):
        target_date = now - timedelta(days=days_offset)
        closest_price = current_price
        min_diff = float('inf')
        for dt, pr in parsed_data:
            diff = abs((dt - target_date).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_price = pr
        return closest_price
        
    return {
        "current": current_price,
        "1D": get_price_at_offset(1),
        "7D": get_price_at_offset(7),
        "30D": get_price_at_offset(30),
        "365D": get_price_at_offset(365)
    }

def format_price_diff(current, old):
    diff = current - old
    if diff > 0:
        return f"📈 +${diff:.2f}"
    elif diff < 0:
        return f"📉 -${abs(diff):.2f}"
    return "➖ b/z"

async def fetch_cs2_commits(session: aiohttp.ClientSession, per_page: int = 3):
    """Pobiera ostatnie commity z repozytorium GameTracking-CS2"""
    url = "https://api.github.com/repos/SteamDatabase/GameTracking-CS2/commits"
    params = {
        "per_page": per_page,
        "page": 1
    }
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Bot-Geekot"
    }
    
    try:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logging.error(f"GitHub API error: {resp.status}")
    except Exception as e:
        logging.error(f"Error fetching CS2 commits: {e}")
    return []

async def fetch_commit_details(session: aiohttp.ClientSession, commit_sha: str):
    """Pobiera szczegóły konkretnego commita"""
    url = f"https://api.github.com/repos/SteamDatabase/GameTracking-CS2/commits/{commit_sha}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Bot-Geekot"
    }
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        logging.error(f"Error fetching commit details: {e}")
    return None

def format_file_changes(files: list) -> str:
    """Formatuje zmiany w plikach na czytelny format - max 1024 znaki"""
    if not files:
        return "Brak informacji o zmianach"
    
    # Filtruj tylko zmienione pliki (modified, added, removed)
    important_files = [f for f in files if f.get("status") in ["modified", "added", "removed"]]
    
    # Jeśli brak ważnych zmian, pokaz sumę
    if not important_files:
        return f"Zmieniono {len(files)} plik(ów)"
    
    formatted = ""
    for file in important_files[:12]:  # Limit do 12 plików
        filename = file.get("filename", "Unknown")
        status = file.get("status", "unknown")
        additions = file.get("additions", 0)
        deletions = file.get("deletions", 0)
        
        # Emoji dla różnych typów zmian
        status_emoji = {
            "added": "✅",
            "removed": "❌",
            "modified": "📝"
        }.get(status, "❓")
        
        change_summary = ""
        if additions > 0:
            change_summary += f"+{additions}"
        if deletions > 0:
            if change_summary:
                change_summary += f"/-{deletions}"
            else:
                change_summary = f"-{deletions}"
        
        # Skracaj nazwy plików jeśli za długie
        if len(filename) > 50:
            filename = filename[:47] + "..."
        
        line = f"{status_emoji} `{filename}`"
        if change_summary:
            line += f" ({change_summary})"
        line += "\n"
        
        # Sprawdzaj czy nie przekroczymy limitu
        if len(formatted) + len(line) > 1000:
            remaining = len(important_files) - (important_files.index(file) + 1)
            if remaining > 0:
                formatted += f"\n... i {remaining} więcej plik(ów)"
            break
        
        formatted += line
    
    return formatted if formatted else f"Zmieniono {len(important_files)} plik(ów)"

@tasks.loop(minutes=15)
async def monitor_cs2_updates_loop():
    """Monitoruje aktualizacje CS2 z GameTracking-CS2"""
    
    try:
        tracking_data = load_cs2_updates_tracking()
        last_commit_sha = tracking_data.get("last_commit_sha")
        
        async with aiohttp.ClientSession() as session:
            commits = await fetch_cs2_commits(session)
            
            if not commits:
                return
            
            latest_commit = commits[0]
            latest_sha = latest_commit.get("sha")
            
            if latest_sha != last_commit_sha:
                commit_details = await fetch_commit_details(session, latest_sha)
                
                if commit_details:
                    tracking_data["last_commit_sha"] = latest_sha
                    tracking_data["last_commit_time"] = datetime.now().isoformat()
                    tracking_data["pending_commits"] = tracking_data.get("pending_commits", [])
                    
                    tracking_data["pending_commits"].append(commit_details)
                    save_cs2_updates_tracking(tracking_data)
                    
                    logging.info(f"Nowa aktualizacja CS2: {commit_details.get('commit', {}).get('message', 'N/A').split(chr(10))[0]}")
    
    except Exception as e:
        logging.error(f"Error in CS2 updates loop: {e}")

@tasks.loop(hours=6)
async def update_steam_history_loop():
    logging.info("Rozpoczęto w tle odświeżanie statystyk skrzynek Steam...")
    
    url = "https://steamcommunity.com/market/search/render/"
    params = {
        "query": "Case",
        "search_descriptions": 0,
        "sort_column": "quantity",
        "sort_dir": "desc",
        "appid": 730,
        "category_730_Type[]": "tag_CSGO_Type_WeaponCase",
        "norender": 1,
        "currency": 6 # PLN
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            all_results = []
            for start_offset in [0, 10, 20]:
                params["start"] = start_offset
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and data.get("success"):
                            all_results.extend(data.get("results", []))
                        else:
                            break
                    else:
                        break
                        
            cases = []
            if all_results:
                for item in all_results:
                    name_lower = item.get("name", "").lower()
                    if "case" in name_lower and "capsule" not in name_lower and "package" not in name_lower:
                        if not any(c.get("name") == item.get("name") for c in cases):
                            cases.append(item)
                    if len(cases) == 15:
                        break
                        
            if not cases:
                logging.error("Steam history worker failed to fetch top cases.")
                return
                
            history_cache = load_steam_history()
            history_cache["top_cases"] = cases 
            history_cache["history"] = history_cache.get("history", {})
            
            for item in cases:
                name = item.get("name")
                raw_history = await fetch_case_history(session, name)
                if raw_history:
                    processed = process_history(raw_history)
                    if processed:
                        processed["sell_price_text"] = item.get("sell_price_text", "?")
                        processed["sell_listings"] = item.get("sell_listings", 0)
                        history_cache["history"][name] = processed
                        
                # Usypiamy bota na moment, by nie łamać rate limtów Steama
                await asyncio.sleep(2)
                
            history_cache["last_updated"] = datetime.now().isoformat()
            save_steam_history(history_cache)
            logging.info("Zakończono zapisywane historii skrzynek Steam.")
            
    except Exception as e:
        logging.error(f"Error in steam history background task: {e}")

async def setup_steam_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int):
    guild_obj = discord.Object(id=guild_id)
    
    if not update_steam_history_loop.is_running():
        update_steam_history_loop.start()
    
    if not monitor_cs2_updates_loop.is_running():
        monitor_cs2_updates_loop.start()
    
    async def send_pending_cs2_updates():
        """Wysyła zakolejkowane aktualizacje CS2 na Discord"""
        tracking_data = load_cs2_updates_tracking()
        pending_commits = tracking_data.get("pending_commits", [])
        
        if not pending_commits:
            return
        
        try:
            channel = client.get_channel(CS2_UPDATES_CHANNEL_ID)
            if not channel:
                logging.error(f"Cannot find CS2 updates channel: {CS2_UPDATES_CHANNEL_ID}")
                return
            
            for commit in pending_commits[:5]:  # Wysyłaj max 5 na raz
                try:
                    commit_msg = commit.get("commit", {}).get("message", "N/A")
                    commit_sha = commit.get("sha", "?")[:7]
                    author = commit.get("commit", {}).get("author", {}).get("name", "Unknown")
                    files = commit.get("files", [])
                    
                    # Pierwsze 50 znaków wiadomości
                    title = commit_msg.split('\n')[0][:100]
                    
                    embed = discord.Embed(
                        title="🎮 CS2 Update",
                        description=f"**{title}**",
                        color=discord.Color.blue(),
                        url=f"https://github.com/SteamDatabase/GameTracking-CS2/commit/{commit.get('sha')}"
                    )
                    
                    embed.add_field(
                        name="Commit SHA",
                        value=f"`{commit_sha}`",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Autor",
                        value=author,
                        inline=True
                    )
                    
                    embed.add_field(
                        name="📁 Zmienione pliki",
                        value=format_file_changes(files),
                        inline=False
                    )
                    
                    # Dodaj linkę do fullmessage jeśli jest wieloliniowa
                    if '\n' in commit_msg:
                        embed.add_field(
                            name="📝 Full Commit",
                            value=f"[Zobacz pełną wiadomość](https://github.com/SteamDatabase/GameTracking-CS2/commit/{commit.get('sha')})",
                            inline=False
                        )
                    
                    embed.set_footer(text="GameTracking-CS2 | SteamDatabase")
                    
                    await channel.send(embed=embed)
                    await asyncio.sleep(1)  # Delay między wiadomościami
                    
                except Exception as e:
                    logging.error(f"Error sending CS2 update: {e}")
            
            # Wyczyść wysłane commity
            tracking_data["pending_commits"] = []
            save_cs2_updates_tracking(tracking_data)
            
        except Exception as e:
            logging.error(f"Error in send_pending_cs2_updates: {e}")
    
    # Dodaj task do wysyłania commitów
    @tasks.loop(seconds=30)
    async def cs2_update_sender():
        await send_pending_cs2_updates()
    
    if not cs2_update_sender.is_running():
        cs2_update_sender.start()

    async def case_autocomplete(interaction: discord.Interaction, current: str):
        history_cache = load_steam_history()
        top_cases = history_cache.get("top_cases", [])
        
        choices = []
        for case_item in top_cases:
            name = case_item.get("name", "")
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
                if len(choices) >= 25:
                    break
        return choices

    @tree.command(name="skrzynki", description="Wyświetla skrzynki na rynku Steam z historią zmian cen", guild=guild_obj)
    @app_commands.autocomplete(nazwa=case_autocomplete)
    @app_commands.describe(nazwa="Wybierz konkretną skrzynkę (opcjonalnie)")
    async def skrzynki(interaction: discord.Interaction, nazwa: str = None):
        await interaction.response.defer()
        
        history_cache = load_steam_history()
        top_cases = history_cache.get("top_cases", [])
        history = history_cache.get("history", {})

        if not top_cases or not history:
            # Jeśli bot się dopiero obudził i loop jeszcze nie skończył
            await interaction.followup.send("⏳ Bot pobiera właśnie pierwsze historyczne wykresy Steama w tle. Z racji limitów odpytań może to potrwać około 30 sekund. Spróbuj powtórzyć komendę za chwilę!")
            return

        if nazwa:
            if nazwa not in history:
                # Dociągnij na żywo z API (brakującą pozycję spoza top15)
                async with aiohttp.ClientSession() as session:
                    raw_history = await fetch_case_history(session, nazwa)
                    if raw_history:
                        processed = process_history(raw_history)
                        if processed:
                            history[nazwa] = processed
                            history[nazwa]["sell_price_text"] = f"${processed['current']:.2f}"
                            history[nazwa]["sell_listings"] = "Brak Info"
                        else:
                            await interaction.followup.send("Przepraszam, nie udało się przetworzyć danych dla tej skrzynki.")
                            return
                    else:
                        await interaction.followup.send("Nie odnaleziono takiej skrzynki, upewnij się że wpisujesz poprawną angielską nazwę.")
                        return

            case_data = history[nazwa]
            
            embed = discord.Embed(title=f"📦 Analiza: {nazwa}", color=discord.Color.gold())
            embed.description = (
                f"**Aktualna wycena:** {case_data.get('sell_price_text')} (Ilość: {case_data.get('sell_listings')})\n\n"
                f"**Historia Zmian:**\n"
                f"📅 **1 Dzień:** {format_price_diff(case_data['current'], case_data['1D'])} (Z ${case_data['1D']:.2f})\n"
                f"📅 **1 Tydzień:** {format_price_diff(case_data['current'], case_data['7D'])} (Z ${case_data['7D']:.2f})\n"
                f"📅 **1 Miesiąc:** {format_price_diff(case_data['current'], case_data['30D'])} (Z ${case_data['30D']:.2f})\n"
                f"📅 **1 Rok:** {format_price_diff(case_data['current'], case_data['365D'])} (Z ${case_data['365D']:.2f})\n"
            )
            embed.set_footer(text="Dane szacownicze pobrane na podstawie wykresu ze Steam Community Market.")
            await interaction.followup.send(embed=embed)
            return

        # Użytkownik chce zsumowaną listę 15
        embed = discord.Embed(title="📦 Najpopularniejsze Skrzynki na Rynku Steam", color=discord.Color.dark_theme())
            
        desc = ""
        for idx, item in enumerate(top_cases, 1):
            name = item.get("name", "Nieznana skrzynka")
            price = item.get("sell_price_text", "?")
            quantity = item.get("sell_listings", 0)
            if isinstance(quantity, int):
                quantity_str = f"{quantity:,}".replace(",", " ")
            else:
                quantity_str = str(quantity)
            
            hist_str = ""
            case_data = history.get(name)
            if case_data:
                d1 = case_data["current"] - case_data["1D"]
                d7 = case_data["current"] - case_data["7D"]
                d365 = case_data["current"] - case_data["365D"]
                
                def sf(d):
                    if d > 0: return f"+${d:.2f}"
                    elif d < 0: return f"-${abs(d):.2f}"
                    return "b/z"
                
                hist_str = f" | 1D: ({sf(d1)}) | 1W: ({sf(d7)}) | 1Y: ({sf(d365)})"

            desc += f"**{idx}.** {name}\n💰 Cena: **{price}**{hist_str}\n📦 Dostępne: **{quantity_str}**\n\n"
        
        embed.description = desc
        embed.set_footer(text="Dane pobrane ze Steam Community Market.")
        
        await interaction.followup.send(embed=embed)
