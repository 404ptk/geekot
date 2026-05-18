import json
import os
from datetime import datetime, timedelta

import discord
from discord.ext import tasks
from faceit.common import format_faceit_form, get_faceit_level_badge, get_guild_emoji_text

FACEIT_LIVE_STATE_FILE = "txt/discordfaceit_live.json"
FACEIT_LIVE_CHANNEL_ID = 1504791638264905778
CLIENT_REF = None


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


def collect_discordfaceit_player_stats():
    import faceit_utils as fu

    player_stats = []

    for nickname in fu.player_nicknames:
        player_data = fu.get_faceit_player_data(nickname)
        if player_data:
            player_level = player_data.get("games", {}).get("cs2", {}).get("skill_level", 0)
            player_elo = player_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0)
            pid = player_data.get("player_id")

            last_matches_str = "N/A"
            streak_emoji = ""
            if pid:
                matches = fu.get_faceit_player_matches(pid, limit=5)
                if matches:
                    outcomes = []
                    for match in matches:
                        result = match.get("stats", {}).get("Result")
                        if result == "1":
                            outcomes.append("W")
                        elif result == "0":
                            outcomes.append("L")
                        else:
                            outcomes.append("?")
                    last_matches_str = "/".join(outcomes)

                    if len(outcomes) >= 3:
                        if outcomes[:3] == ["W", "W", "W"]:
                            streak_emoji = " 🔥"
                        elif outcomes[:3] == ["L", "L", "L"]:
                            streak_emoji = " 😭"

            player_stats.append(
                {
                    "nickname": nickname,
                    "level": player_level if isinstance(player_level, int) else 0,
                    "elo": player_elo if isinstance(player_elo, int) else 0,
                    "last_matches_raw": last_matches_str,
                    "last_matches": format_faceit_form(last_matches_str.split("/")) if last_matches_str != "N/A" else "⚪",
                    "streak_emoji": streak_emoji,
                }
            )

    player_stats.sort(key=lambda x: (x["elo"], x["level"]), reverse=True)
    return player_stats


def build_discordfaceit_live_embed(guild):
    import faceit_utils as fu

    player_stats = collect_discordfaceit_player_stats()
    footer_now = (datetime.now() + timedelta(hours=2)).strftime("%H:%M:%S")
    daily_stats = fu.load_daily_stats()
    current_date = datetime.now().strftime("%Y-%m-%d")

    max_nickname_len = max((len(player["nickname"]) for player in player_stats[:10]), default=0)
    max_elo_len = max((len(str(player["elo"])) for player in player_stats[:10]), default=0)
    max_daily_len = max(
        (
            len(
                f"{'+' if (player['elo'] - daily_stats.get('stats', {}).get(player['nickname'], player['elo'])) > 0 else ''}{player['elo'] - daily_stats.get('stats', {}).get(player['nickname'], player['elo'])}"
                if daily_stats.get("date") == current_date
                else "0"
            )
            for player in player_stats[:10]
            if isinstance(player.get("elo"), int)
        ),
        default=1,
    )

    lines = ["", ""]
    for index, player in enumerate(player_stats[:10], start=1):
        level_badge = get_faceit_level_badge(guild, player["level"])
        daily_elo_change = "0"
        if daily_stats.get("date") == current_date:
            start_elo = daily_stats.get("stats", {}).get(player["nickname"])
            if start_elo is not None and isinstance(player["elo"], int):
                elo_diff = player["elo"] - start_elo
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

    message = None
    try:
        async for msg in channel.history(limit=10):
            if msg.author == CLIENT_REF.user:
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

    try:
        message = await channel.send(embed=embed)
        try:
            await message.pin()
        except (discord.Forbidden, discord.HTTPException):
            pass

        save_faceit_live_state({"channel_id": channel.id, "message_id": message.id})
    except discord.HTTPException as exc:
        print(f"Nie udało się odświeżyć Faceit live: {exc}")


@tasks.loop(minutes=1)
async def track_discordfaceit_live():
    await refresh_discordfaceit_live_message()


async def start_faceit_live_tracking(client):
    global CLIENT_REF
    CLIENT_REF = client

    if not track_discordfaceit_live.is_running():
        track_discordfaceit_live.start()

    await refresh_discordfaceit_live_message()
