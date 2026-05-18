import requests
import json
import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta
import asyncio
import os
from startup_logger import record_startup_step

GUILD_ID = 551503797067710504

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

FACEIT_API_KEY = load_token('txt/faceit_api.txt', startup_label="Faceit API token")

# Lista pseudonimów graczy do rankingu Discorda
player_nicknames = ['utopiasz', 'radzioswir', 'PhesterM9', '-Masny-', '-mateuko', 'Kvzia', 'Kajetov', 'MlodyHubii']

FACEIT_RANKING_FILE = "txt/faceit_ranking.txt"
FACEIT_DAILY_STATS_FILE = "txt/faceit_daily_stats.json"
FACEIT_WEEKLY_STATS_FILE = "txt/faceit_weekly_stats.json"
FACEIT_LIVE_STATE_FILE = "txt/discordfaceit_live.json"
FACEIT_LIVE_CHANNEL_ID = 1504791638264905778
CLIENT_REF = None  # Reference to the Discord client for background tasks

def get_guild_emoji_text(guild, emoji_name):
    if not guild:
        return ""

    emoji_obj = discord.utils.get(guild.emojis, name=emoji_name)
    return str(emoji_obj) if emoji_obj else ""


def load_faceit_live_state():
    if os.path.exists(FACEIT_LIVE_STATE_FILE):
        try:
            with open(FACEIT_LIVE_STATE_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_faceit_live_state(data):
    with open(FACEIT_LIVE_STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def get_faceit_level_badge(guild, level):
    if isinstance(level, int) and level > 0:
        emoji_text = get_guild_emoji_text(guild, f"faceit{level}")
        if emoji_text:
            return emoji_text
        return f"LVL {level}"
    return "❓"


def format_faceit_form(outcomes):
    if not outcomes:
        return "❓"

    emoji_map = {
        "W": "🟢",
        "L": "🔴",
        "?": "⚪",
    }
    return " ".join(emoji_map.get(outcome, "⚪") for outcome in outcomes)


def collect_discordfaceit_player_stats():
    player_stats = []

    for nickname in player_nicknames:
        player_data = get_faceit_player_data(nickname)
        if player_data:
            player_level = player_data.get('games', {}).get('cs2', {}).get('skill_level', 0)
            player_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', 0)
            pid = player_data.get('player_id')

            last_matches_str = "N/A"
            streak_emoji = ""
            if pid:
                matches = get_faceit_player_matches(pid, limit=5)
                if matches:
                    outcomes = []
                    for match in matches:
                        result = match.get('stats', {}).get('Result')
                        if result == '1':
                            outcomes.append('W')
                        elif result == '0':
                            outcomes.append('L')
                        else:
                            outcomes.append('?')
                    last_matches_str = '/'.join(outcomes)

                    if len(outcomes) >= 3:
                        if outcomes[:3] == ['W', 'W', 'W']:
                            streak_emoji = " 🔥"
                        elif outcomes[:3] == ['L', 'L', 'L']:
                            streak_emoji = " 😭"

            player_stats.append({
                'nickname': nickname,
                'level': player_level if isinstance(player_level, int) else 0,
                'elo': player_elo if isinstance(player_elo, int) else 0,
                'last_matches_raw': last_matches_str,
                'last_matches': format_faceit_form(last_matches_str.split('/')) if last_matches_str != "N/A" else "⚪",
                'streak_emoji': streak_emoji,
            })

    player_stats.sort(key=lambda x: (x['elo'], x['level']), reverse=True)
    return player_stats


def build_discordfaceit_live_embed(guild):
    player_stats = collect_discordfaceit_player_stats()
    now = datetime.now().strftime("%H:%M:%S")
    footer_now = (datetime.now() + timedelta(hours=2)).strftime("%H:%M:%S")
    daily_stats = load_daily_stats()
    current_date = datetime.now().strftime("%Y-%m-%d")
    max_nickname_len = max((len(player['nickname']) for player in player_stats[:10]), default=0)
    max_elo_len = max((len(str(player['elo'])) for player in player_stats[:10]), default=0)
    max_daily_len = max(
        (
            len(
                f"{'+' if (player['elo'] - daily_stats.get('stats', {}).get(player['nickname'], player['elo'])) > 0 else ''}{player['elo'] - daily_stats.get('stats', {}).get(player['nickname'], player['elo'])}"
                if daily_stats.get('date') == current_date else "0"
            )
            for player in player_stats[:10]
            if isinstance(player.get('elo'), int)
        ),
        default=1,
    )

    lines = ["", ""]
    for index, player in enumerate(player_stats[:10], start=1):
        level_badge = get_faceit_level_badge(guild, player['level'])
        daily_elo_change = "0"
        if daily_stats.get("date") == current_date:
            start_elo = daily_stats.get("stats", {}).get(player['nickname'])
            if start_elo is not None and isinstance(player['elo'], int):
                elo_diff = player['elo'] - start_elo
                daily_elo_change = f"{'+' if elo_diff > 0 else ''}{elo_diff}" if elo_diff != 0 else "0"
        lines.append(
            f"**{index}.** {level_badge} `{player['nickname']:<{max_nickname_len}} | {player['elo']:>{max_elo_len}} ELO | {daily_elo_change:>{max_daily_len}} | {player['last_matches']}`"
        )

    faceit_logo = get_guild_emoji_text(guild, "faceitlogo")
    title_prefix = f"{faceit_logo} " if faceit_logo else ""

    embed = discord.Embed(
        title=f"{title_prefix} **FACEIT LIVE**",
        description="\n".join(lines),
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"Odświeżanie co 60s • {footer_now}")
    return embed

def get_faceit_player_data(nickname):
    url = f'https://open.faceit.com/data/v4/players?nickname={nickname}'
    headers = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def get_faceit_player_matches(player_id, limit=5):
    game_id = "cs2"
    url = f'https://open.faceit.com/data/v4/players/{player_id}/games/{game_id}/stats?limit={limit}'
    headers = {'Authorization': f'Bearer {FACEIT_API_KEY}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('items', [])
    else:
        print("Błąd połączenia z Faceit API:", response.status_code)
        return None

def save_faceit_ranking(player_stats):
    with open(FACEIT_RANKING_FILE, "w") as file:
        json.dump(player_stats, file)

def load_faceit_ranking():
    try:
        with open(FACEIT_RANKING_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_faceit_match_details(match_id):
    url = f"https://open.faceit.com/data/v4/matches/{match_id}/stats"
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    match_data = response.json()
    teams = {}
    for team in match_data["rounds"][0]["teams"]:
        team_name = team["team_id"]
        teams[team_name] = {"players": []}
        for player in team["players"]:
            teams[team_name]["players"].append({
                "nickname": player["nickname"],
                "kills": int(player["player_stats"]["Kills"]),
                "deaths": int(player["player_stats"]["Deaths"]),
                "assists": int(player["player_stats"]["Assists"]),
                "headshots": int(player["player_stats"]["Headshots %"]),
                "adr": player["player_stats"].get("ADR", "0"),
                "multikills": {
                    "2k": int(player["player_stats"].get("Double Kills", 0)),
                    "3k": int(player["player_stats"].get("Triple Kills", 0)),
                    "4k": int(player["player_stats"].get("Quadro Kills", 0)),
                    "5k": int(player["player_stats"].get("Penta Kills", 0))
                },
                "entry": {
                    "count": int(player["player_stats"].get("Entry Count", 0)),
                    "wins": int(player["player_stats"].get("Entry Wins", 0))
                },
                "clutch": {
                    "count": int(player["player_stats"].get("1v1Count", 0)) + int(player["player_stats"].get("1v2Count", 0)),
                    "wins": int(player["player_stats"].get("1v1Wins", 0)) + int(player["player_stats"].get("1v2Wins", 0))
                },
                "flash": {
                    "count": int(player["player_stats"].get("Flash Count", 0)),
                    "successes": int(player["player_stats"].get("Flash Successes", 0))
                },
                "utility_dmg": int(player["player_stats"].get("Utility Damage", 0)),
                "kr_ratio": player["player_stats"].get("K/R Ratio", "0"),
                "mvps": int(player["player_stats"].get("MVPs", 0)),
            })
    # Determine final score (e.g., 13:11)
    score = None
    try:
        round_stats = match_data.get("rounds", [{}])[0].get("round_stats", {})
        score_raw = round_stats.get("Score")
        if score_raw:
            score = score_raw.replace(" ", "").replace("/", ":")
        else:
            # Fallback: read from team_stats if available
            teams_list = match_data.get("rounds", [{}])[0].get("teams", [])
            if len(teams_list) == 2:
                t1 = teams_list[0].get("team_stats", {})
                t2 = teams_list[1].get("team_stats", {})
                s1 = t1.get("Final Score") or t1.get("Score") or t1.get("Team Score")
                s2 = t2.get("Final Score") or t2.get("Score") or t2.get("Team Score")
                if s1 and s2:
                    score = f"{s1}:{s2}"
    except Exception:
        pass
    return {
        "map": match_data["rounds"][0]["round_stats"]["Map"],
        "teams": teams,
        "score": score,
    }

def get_faceit_match_roster(match_id):
    """Fetches match roster with level for all players (1 API call).
    ELO is fetched only for players in player_nicknames to minimize API calls."""
    url = f"https://open.faceit.com/data/v4/matches/{match_id}"
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return {}
    data = response.json()
    roster = {}
    for team_key in ["faction1", "faction2"]:
        team = data.get("teams", {}).get(team_key, {})
        for player in team.get("roster", []):
            nick = player.get("nickname", "")
            level = player.get("game_skill_level", 0)
            roster[nick] = {
                "elo": "",
                "level": level,
            }
    # Fetch ELO for all players
    for nick in roster:
        p_data = get_faceit_player_data(nick)
        if p_data:
            elo = p_data.get('games', {}).get('cs2', {}).get('faceit_elo', '')
            roster[nick]["elo"] = str(elo)
    return roster

def reset_faceit_ranking():
    if os.path.exists(FACEIT_RANKING_FILE):
        os.remove(FACEIT_RANKING_FILE)

def load_daily_stats():
    if os.path.exists(FACEIT_DAILY_STATS_FILE):
        try:
            with open(FACEIT_DAILY_STATS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_daily_stats(data):
    with open(FACEIT_DAILY_STATS_FILE, "w") as f:
        json.dump(data, f)

def load_weekly_stats():
    if os.path.exists(FACEIT_WEEKLY_STATS_FILE):
        try:
            with open(FACEIT_WEEKLY_STATS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_weekly_stats(data):
    with open(FACEIT_WEEKLY_STATS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_matches_in_period(player_id, start_ts, end_ts):
    """
    Fetches matches for a player and filters them by timestamp.
    start_ts and end_ts are in seconds.
    """
    # Fetch enough matches to cover the week. 50 should be plenty for most non-pro players.
    limit = 50 
    matches = get_faceit_player_matches(player_id, limit=limit)
    
    if not matches:
        return []
    
    filtered_matches = []
    for match in matches:
        match_stats = match.get('stats', {})
        # 'Match Finished At' is in milliseconds
        finished_at_ms = match_stats.get('Match Finished At') 
        
        if finished_at_ms:
            finished_at_sec = int(finished_at_ms) / 1000.0
            if start_ts <= finished_at_sec <= end_ts:
                filtered_matches.append(match)
    
    return filtered_matches

def calculate_weekly_metrics(matches):
    if not matches:
        return None
    
    count = len(matches)
    wins = 0
    total_kills = 0
    total_deaths = 0
    total_adr = 0.0
    
    for m in matches:
        stats = m.get('stats', {})
        total_kills += int(stats.get('Kills', 0))
        total_deaths += int(stats.get('Deaths', 0))
        total_adr += float(stats.get('ADR', 0))
        if stats.get('Result') == '1':
            wins += 1
            
    losses = count - wins
    avg_kills = total_kills / count
    avg_adr = total_adr / count
    kd = total_kills / total_deaths if total_deaths > 0 else float(total_kills)
    winratio = (wins / count) * 100
    
    return {
        "count": count,
        "wins": wins,
        "losses": losses,
        "total_kills": total_kills,
        "avg_kills": avg_kills,
        "avg_adr": avg_adr,
        "kd": kd,
        "winratio": winratio
    }

def create_weekly_stats_embed(start_ts, end_ts, snapshot_elos, title, description):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )

    player_stats_list = []

    for nickname in player_nicknames:
        player_data = get_faceit_player_data(nickname)
        if not player_data:
            continue
            
        pid = player_data.get('player_id')
        current_elo = player_data.get('games', {}).get('cs2', {}).get('faceit_elo', 0)
        
        if not pid:
            continue

        matches = get_matches_in_period(pid, start_ts, end_ts)
        metrics = calculate_weekly_metrics(matches)
        
        # ELO Diff
        elo_diff_str = ""
        elo_diff_val = 0
        start_elo = snapshot_elos.get(nickname)
        if start_elo is not None and isinstance(current_elo, int):
            diff = current_elo - start_elo
            elo_diff_val = diff
            elo_diff_str = f"{start_elo} -> {current_elo} ({'+' if diff > 0 else ''}{diff})"
        else:
            elo_diff_str = f"{current_elo}"

        player_stats_list.append({
            "nick": nickname,
            "metrics": metrics,
            "elo_str": elo_diff_str,
            "elo_diff": elo_diff_val
        })

    # Sort: Players with matches first (by count desc), then others
    player_stats_list.sort(key=lambda x: (x['metrics']['count'] if x['metrics'] else -1), reverse=True)

    for p in player_stats_list:
        m = p['metrics']
        if not m:
            # val = "Nie rozegrał w tym tygodniu żadnego meczu."
            continue
        else:
            val = (
                f"```ELO: {p['elo_str']} | Gier: {m['count']}```"
                f"```Śr. K/D: {m['kd']:.2f} | Śr. kille: {m['avg_kills']:.1f} | Śr. ADR: {m['avg_adr']:.1f}```"
            )
        embed.add_field(name=f"👤 {p['nick']}", value=val, inline=False)
    
    embed.set_footer(text="Jeśli nie ma cię na liście, to znaczy że nie rozegrałeś żadnego meczu w tym tygodniu.")

    # --- AWARDS SECTION ---
    active_players = [p for p in player_stats_list if p['metrics']]
    
    if active_players:
        embed.add_field(name="", value="Statystyki specjalne:", inline=False)
        
        # Helper to format line
        def fmt(label, nick, extra):
            return f"**{label}:** {nick} | {extra}"

        # GOAT: (kd*100 + adr) max
        goat = max(active_players, key=lambda p: p['metrics']['kd']*100 + p['metrics']['avg_adr'])
        embed.add_field(name="🐐 GOAT tygodnia", 
                        value=f"{goat['nick']} | K/D: {goat['metrics']['kd']:.2f} | ADR: {goat['metrics']['avg_adr']:.1f}", inline=False)

        # Troll: (kd*100 + adr) min
        troll = min(active_players, key=lambda p: p['metrics']['kd']*100 + p['metrics']['avg_adr'])
        embed.add_field(name="🤡 Troll tygodnia", 
                        value=f"{troll['nick']} | K/D: {troll['metrics']['kd']:.2f} | ADR: {troll['metrics']['avg_adr']:.1f}", inline=False)

        # Bezrobotny: Max games
        bezrobotny = max(active_players, key=lambda p: p['metrics']['count'])
        embed.add_field(name="🛌 Bezrobotny tygodnia", 
                        value=f"{bezrobotny['nick']} | Gier: {bezrobotny['metrics']['count']}", inline=False)

        # Syzyf: Biggest negative elo diff
        # Filter only negative diffs
        negative_diffs = [p for p in active_players if p['elo_diff'] < 0]
        if negative_diffs:
            syzyf = min(negative_diffs, key=lambda p: p['elo_diff']) # Most negative number is minimum
            embed.add_field(name="🪨 Syzyf tygodnia", 
                            value=f"{syzyf['nick']} | {syzyf['elo_diff']}", inline=False)

        # Best ADR
        best_adr = max(active_players, key=lambda p: p['metrics']['avg_adr'])
        embed.add_field(name="🔫 Najlepszy ADR", 
                        value=f"{best_adr['nick']} | {best_adr['metrics']['avg_adr']:.1f}", inline=False)
        
        # Most Kills (Avg)
        most_kills_avg = max(active_players, key=lambda p: p['metrics']['avg_kills'])
        embed.add_field(name="💀 Najwięcej zabójstw (śr.)", 
                        value=f"{most_kills_avg['nick']} | {most_kills_avg['metrics']['avg_kills']:.1f}", inline=False)

    return embed

async def generate_weekly_summary(client, channel_id=None):
    """
    Generates the weekly summary embed.
    If run automatically (Monday), it compares with saved snapshot.
    """
    weekly_stats = load_weekly_stats()
    
    # Check "last valid snapshot"
    if not weekly_stats:
        return None

    last_snapshot_date_str = weekly_stats.get("date")
    snapshot_elos = weekly_stats.get("stats", {})
    
    if last_snapshot_date_str:
        try:
            start_dt = datetime.strptime(last_snapshot_date_str, "%Y-%m-%d")
        except ValueError:
            start_dt = datetime.now() - timedelta(days=7)
    else:
        start_dt = datetime.now() - timedelta(days=7)

    end_dt = datetime.now()
    start_ts = start_dt.timestamp()
    end_ts = end_dt.timestamp()

    return create_weekly_stats_embed(
        start_ts, 
        end_ts, 
        snapshot_elos,
        "📅 **Podsumowanie Tygodnia Faceit**",
        f"Statystyki za okres: {start_dt.strftime('%Y-%m-%d')} - {end_dt.strftime('%Y-%m-%d')}"
    )

# ----------------- SCHEDULED TASKS -----------------

@tasks.loop(minutes=10)
async def track_daily_elo():
    # Only run checks if client is ready
    if not CLIENT_REF or not CLIENT_REF.is_ready():
        return

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # --- WEEKLY SUMMARY (Monday) ---
    weekly_stats = load_weekly_stats()
    last_run_date = weekly_stats.get("last_run_date")

    # If it is Monday and we haven't run yet today
    if now.weekday() == 0 and last_run_date != today_str:
        # Channel ID for weekly summary
        target_channel_id = 1301248598108798996
        
        channel = CLIENT_REF.get_channel(target_channel_id)
        if channel:
             last_snapshot_date_str = weekly_stats.get("date")
             try:
                 start_dt = datetime.strptime(last_snapshot_date_str, "%Y-%m-%d") if last_snapshot_date_str else (now - timedelta(days=7))
             except ValueError:
                 start_dt = now - timedelta(days=7)

             start_ts = start_dt.timestamp()
             end_ts = now.timestamp()
             snapshot_elos = weekly_stats.get("stats", {})

             # Generate Summary
             embed = create_weekly_stats_embed(
                start_ts,
                end_ts,
                snapshot_elos,
                "📅 **Podsumowanie Tygodnia Faceit**",
                f"Statystyki za okres: {start_dt.strftime('%d-%m-%Y')} - {today_str}"
             )
             
             if embed:
                 await channel.send(embed=embed)
                 
                 # UPDATE SNAPSHOT for next week
                 # Save current ELOs as new snapshot
                 new_snapshot = {}
                 for nick in player_nicknames:
                     p_data = get_faceit_player_data(nick)
                     if p_data:
                         elo = p_data.get('games', {}).get('cs2', {}).get('faceit_elo')
                         if isinstance(elo, int):
                             new_snapshot[nick] = elo
                 
                 weekly_stats["stats"] = new_snapshot
                 weekly_stats["date"] = today_str # Snapshot date
                 weekly_stats["last_run_date"] = today_str 
                 save_weekly_stats(weekly_stats)
                 
    # --- DAILY STATS (for comparison) ---
    daily_stats = load_daily_stats()
    if daily_stats.get("date") != today_str:
        # It's a new day, save current ELOs
        new_daily = {}
        for nick in player_nicknames:
            p_data = get_faceit_player_data(nick)
            if p_data:
                elo = p_data.get('games', {}).get('cs2', {}).get('faceit_elo')
                if isinstance(elo, int):
                    new_daily[nick] = elo
        
        daily_stats = {
            "date": today_str,
            "stats": new_daily
        }
        with open(FACEIT_DAILY_STATS_FILE, "w") as f:
            json.dump(daily_stats, f)


async def refresh_discordfaceit_live_message():
    if not CLIENT_REF or not CLIENT_REF.is_ready():
        return

    channel = CLIENT_REF.get_channel(FACEIT_LIVE_CHANNEL_ID)
    if channel is None:
        try:
            channel = await CLIENT_REF.fetch_channel(FACEIT_LIVE_CHANNEL_ID)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            return

    if channel is None or not hasattr(channel, "send"):
        return

    embed = build_discordfaceit_live_embed(getattr(channel, "guild", None))
    
    # Szukamy ostatnią wiadomość od bota na kanale (zamiast polegać na cache)
    message = None
    try:
        async for msg in channel.history(limit=10):
            # Szukamy wiadomości od bota (bez autora lub od tego samego bota)
            if msg.author == CLIENT_REF.user:
                # To jest wiadomość od naszego bota
                message = msg
                break
    except (discord.Forbidden, discord.HTTPException):
        pass

    if message:
        try:
            await message.edit(embed=embed)
            return
        except discord.HTTPException:
            message = None

    # Jeśli nie ma starej wiadomości, wysyłamy nową
    try:
        message = await channel.send(embed=embed)
        try:
            # Pinujemy wiadomość jeśli to możliwe
            await message.pin()
        except (discord.Forbidden, discord.HTTPException):
            pass
        # Opcjonalnie: zapisujemy state jako backup
        save_faceit_live_state({"channel_id": channel.id, "message_id": message.id})
    except discord.HTTPException as exc:
        print(f"Nie udało się odświeżyć Faceit live: {exc}")


@tasks.loop(minutes=1)
async def track_discordfaceit_live():
    await refresh_discordfaceit_live_message()

# ----------------- SLASH COMMANDS -----------------

async def setup_faceit_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    global CLIENT_REF
    CLIENT_REF = client
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    # Autocomplete callback for Faceit nickname
    async def faceit_nick_autocomplete(interaction: discord.Interaction, current: str):
        query = (current or "").lower()
        options = [n for n in player_nicknames if query in n.lower()]
        return [app_commands.Choice(name=n, value=n) for n in options[:25]]

    from faceit.faceit import register_faceit_command

    register_faceit_command(
        tree=tree,
        guild=guild,
        faceit_nick_autocomplete=faceit_nick_autocomplete,
    )

    from faceit.last import register_last_command

    register_last_command(
        tree=tree,
        guild=guild,
        faceit_nick_autocomplete=faceit_nick_autocomplete,
    )

    from faceit.discordfaceit import register_discordfaceit_command

    register_discordfaceit_command(
        tree=tree,
        guild=guild,
    )

    @tree.command(
        name="resetfaceitranking",
        description="Resetuje ranking Faceit (czyści plik rankingowy)",
        guild=guild
    )
    async def resetfaceitranking(interaction: discord.Interaction):
        reset_faceit_ranking()
        await interaction.response.send_message("✅ Ranking Faceit został zresetowany (plik faceit_ranking.txt usunięty).", ephemeral=True)

    if not track_daily_elo.is_running():
        track_daily_elo.start()

    if not track_discordfaceit_live.is_running():
        track_discordfaceit_live.start()
    await refresh_discordfaceit_live_message()

    from faceit.sieroty import register_sieroty_commands

    register_sieroty_commands(
        tree=tree,
        guild=guild,
        faceit_nick_autocomplete=faceit_nick_autocomplete,
    )

MASNY_FILE = "txt/masny.txt"

# Zdjęcia dla miejsc 1-5
image_links = {
    "1": "https://cdn.discordapp.com/attachments/809156611167748176/1330901097816129596/BE8227A4-FD7F-42E4-A48F-350CD124D92B.png?ex=678fa9bc&is=678e583c&hm=ac937a4d34a9375cc56fefdbb1d228733a3fdf0daaaa720e5a020ecd302a878e&",
    "2": "https://cdn.discordapp.com/attachments/809156611167748176/1330905145772474428/61A0B076-BD51-400C-AF19-A7B1D626B1B1.png?ex=678fad81&is=678e5c01&hm=6f06532e17ca3e49d550adc2cf84ff19f80b91e5b7b8833c7c7dc54061f40882&",
    "3": "https://cdn.discordapp.com/attachments/809156611167748176/1330911802049036340/2698389E-237A-4840-8A63-07F996640858.png?ex=678fb3b4&is=678e6234&hm=4870f7636f0053600f02e59e2c9332c5c0272d04e8cb25d25ad643c6f2947739&",
    "4": "https://media.discordapp.net/attachments/778302928338550865/1300471813146415176/B4B5C4D4-8E00-43CE-927B-E9CC47FB2201.png?ex=678fb441&is=678e62c1&hm=661a9436fdf6bbe526df0afa62a28adf1ae8a4dbca4dab0f333d4a4c059d9a0d&=&format=webp&quality=lossless&width=359&height=601",
    "5": "https://cdn.discordapp.com/attachments/809156611167748176/1330906894302318592/pobrane_1.gif?ex=678faf22&is=678e5da2&hm=908f4934957c128b1531edc28da1820b096fd8a1bd35358621e794336969884e&"
}

def load_masny_data():
    # Zwraca słownik {"1": 0, "2": 0, ...}
    if os.path.exists(MASNY_FILE):
        try:
            with open(MASNY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for i in range(1, 6):
                    data.setdefault(str(i), 0)
                return data
        except Exception:
            pass
    return {str(i): 0 for i in range(1, 6)}

def save_masny_data(data):
    with open(MASNY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)