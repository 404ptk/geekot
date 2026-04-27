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
