from datetime import datetime, timedelta, timezone
from typing import Callable

import discord


def adjusted_now(offset_hours: int = 0) -> datetime:
    return datetime.now() + timedelta(hours=offset_hours)


def today_str(offset_hours: int = 0) -> str:
    return adjusted_now(offset_hours).strftime("%Y-%m-%d")


def is_within_send_window(
    send_hour: int,
    window_hours: int = 2,
    offset_hours: int = 0,
) -> bool:
    hour = adjusted_now(offset_hours).hour
    return send_hour <= hour < send_hour + window_hours


def is_message_from_today(message: discord.Message, offset_hours: int = 0) -> bool:
    local_today = adjusted_now(offset_hours).date()
    msg_local = (message.created_at.replace(tzinfo=timezone.utc) + timedelta(hours=offset_hours)).date()
    return msg_local == local_today


async def already_sent_today(
    client: discord.Client,
    channel_id: int,
    embed_title_contains: str,
    state: dict,
    save_state: Callable[[dict], None],
    offset_hours: int = 0,
    state_key: str = "last_run_date",
) -> bool:
    today = today_str(offset_hours)
    if state.get(state_key) == today:
        return True

    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except Exception:
            return False

    try:
        async for message in channel.history(limit=50):
            if message.author.id != client.user.id:
                continue
            if not is_message_from_today(message, offset_hours):
                continue
            for embed in message.embeds:
                title = embed.title or ""
                if embed_title_contains in title:
                    state[state_key] = today
                    save_state(state)
                    return True
    except Exception as exc:
        print(f"[DailyGuard] Channel history check failed: {exc}")

    return False


def mark_sent_today(
    state: dict,
    save_state: Callable[[dict], None],
    offset_hours: int = 0,
    state_key: str = "last_run_date",
) -> None:
    state[state_key] = today_str(offset_hours)
    save_state(state)
