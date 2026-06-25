import asyncio
from datetime import datetime, timezone

import discord

from jobs.api_status import build_status_embed, check_all_services
from jobs.config import load_config
from jobs.constants import API_STATUS_INTERVAL_MINUTES, API_STATUS_MESSAGE_ID
from jobs.discord_utils import get_discord_channel

_update_lock = asyncio.Lock()
_running_tasks = []


async def update_api_status_message(client: discord.Client):
    async with _update_lock:
        config = load_config()
        channel = await get_discord_channel(client, int(config["discord_channel_id"]))
        if not channel:
            print("[Jobs] Cannot update API status message - channel not found")
            return

        results = await asyncio.to_thread(check_all_services)
        checked_at = datetime.now(timezone.utc)
        embed = build_status_embed(results, checked_at)

        try:
            message = await channel.fetch_message(API_STATUS_MESSAGE_ID)
            await message.edit(embed=embed)
            print("[Jobs] API status message updated.")
        except discord.NotFound:
            print(f"[Jobs] API status message {API_STATUS_MESSAGE_ID} not found.")
        except Exception as exc:
            print(f"[Jobs] Failed to update API status message: {exc}")


async def status_worker(client: discord.Client):
    await asyncio.sleep(15)
    while True:
        await update_api_status_message(client)
        await asyncio.sleep(API_STATUS_INTERVAL_MINUTES * 60)


def start_api_status_worker(client: discord.Client):
    task = asyncio.create_task(status_worker(client))
    _running_tasks.append(task)
    print(
        f"[Jobs] API status worker started "
        f"(message {API_STATUS_MESSAGE_ID}, every {API_STATUS_INTERVAL_MINUTES} min)"
    )
