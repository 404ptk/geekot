import asyncio
from datetime import datetime, timezone

import discord

from jobs.api_status import build_status_embed, check_all_services
from jobs.config import load_config
from jobs.constants import API_STATUS_INTERVAL_MINUTES
from jobs.discord_utils import get_discord_channel
from jobs.state import load_state, save_state

_sticky_lock = asyncio.Lock()
_running_tasks = []


async def refresh_sticky_status(client: discord.Client, channel_id: int = None):
    async with _sticky_lock:
        config = load_config()
        if channel_id is None:
            channel_id = int(config["discord_channel_id"])

        channel = await get_discord_channel(client, channel_id)
        if not channel:
            print(f"[Jobs] Cannot refresh API status sticky - channel {channel_id} not found")
            return

        results = await asyncio.to_thread(check_all_services)
        checked_at = datetime.now(timezone.utc)
        embed = build_status_embed(results, checked_at)

        state = load_state()
        old_message_id = state.get("sticky_status_message_id")
        if old_message_id:
            try:
                old_message = await channel.fetch_message(old_message_id)
                await old_message.delete()
            except discord.NotFound:
                pass
            except Exception as exc:
                print(f"[Jobs] Failed to delete old API status sticky: {exc}")

        try:
            message = await channel.send(embed=embed)
            state["sticky_status_message_id"] = message.id
            state["api_status_last_check"] = checked_at.isoformat()
            state["api_status_results"] = results
            save_state(state)
            print("[Jobs] API status sticky refreshed.")
        except Exception as exc:
            print(f"[Jobs] Failed to post API status sticky: {exc}")


async def status_worker(client: discord.Client):
    await asyncio.sleep(15)
    while True:
        await refresh_sticky_status(client)
        await asyncio.sleep(API_STATUS_INTERVAL_MINUTES * 60)


def start_status_worker(client: discord.Client):
    task = asyncio.create_task(status_worker(client))
    _running_tasks.append(task)
    print(f"[Jobs] API status sticky worker started (every {API_STATUS_INTERVAL_MINUTES} min)")
