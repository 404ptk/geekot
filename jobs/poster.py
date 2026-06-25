import asyncio
from typing import Any, Dict, List

import discord

from jobs.config import load_config
from jobs.constants import (
    API_STATUS_MESSAGE_ID,
    BULK_POST_DELAY_SECONDS,
    BULK_POST_THRESHOLD,
    DISMISS_EMOJI,
    NORMAL_POST_DELAY_SECONDS,
)
from jobs.discord_utils import get_discord_channel
from jobs.embeds import build_offer_embed


def post_delay_seconds(offer_count: int) -> float:
    if offer_count > BULK_POST_THRESHOLD:
        return BULK_POST_DELAY_SECONDS
    return NORMAL_POST_DELAY_SECONDS


async def post_offers(client: discord.Client, offers: List[Dict[str, Any]], channel_id: int):
    channel = await get_discord_channel(client, channel_id)
    if not channel:
        print(f"[Jobs] Cannot find Discord channel {channel_id}")
        return

    delay_seconds = post_delay_seconds(len(offers))
    if len(offers) > BULK_POST_THRESHOLD:
        print(
            f"[Jobs] Bulk post mode: {len(offers)} offers, "
            f"waiting {delay_seconds}s between messages."
        )

    posted = 0
    failed = 0
    for index, offer in enumerate(offers, start=1):
        try:
            message = await channel.send(embed=build_offer_embed(offer))
            try:
                await message.add_reaction(DISMISS_EMOJI)
            except Exception as e:
                print(f"[Jobs] Failed to add dismiss reaction: {e}")
            posted += 1
        except Exception as e:
            failed += 1
            print(f"[Jobs] Failed to post offer {offer.get('offer_uuid')}: {e}")

        if index < len(offers):
            await asyncio.sleep(delay_seconds)

    print(f"[Jobs] Posted {posted}/{len(offers)} offer(s)" + (f", {failed} failed" if failed else ""))


async def handle_dismiss_reaction(client: discord.Client, payload: discord.RawReactionActionEvent):
    if str(payload.emoji) != DISMISS_EMOJI:
        return
    if payload.user_id == client.user.id:
        return

    config = load_config()
    if payload.channel_id != int(config.get("discord_channel_id", 0)):
        return

    channel = client.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(payload.channel_id)
        except Exception:
            return

    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        return

    if not message.author or message.author.id != client.user.id:
        return
    if not message.embeds:
        return

    if payload.message_id == API_STATUS_MESSAGE_ID:
        return

    try:
        await message.delete()
    except Exception as e:
        print(f"[Jobs] Failed to delete dismissed offer message {payload.message_id}: {e}")


def register_dismiss_listener(client: discord.Client):
    if getattr(client, "_jobs_reaction_listener_registered", False):
        return

    async def on_jobs_reaction_add(payload: discord.RawReactionActionEvent):
        await handle_dismiss_reaction(client, payload)

    client.add_listener(on_jobs_reaction_add, "on_raw_reaction_add")
    client._jobs_reaction_listener_registered = True
