import asyncio
from typing import Any, Dict, List

import discord

from jobs.config import load_config
from jobs.constants import DISMISS_EMOJI
from jobs.embeds import build_offer_embed


async def get_discord_channel(client: discord.Client, channel_id: int):
    channel = client.get_channel(channel_id)
    if channel:
        return channel
    try:
        return await client.fetch_channel(channel_id)
    except Exception:
        return None


async def post_offers(client: discord.Client, offers: List[Dict[str, Any]], channel_id: int):
    channel = await get_discord_channel(client, channel_id)
    if not channel:
        print(f"[Jobs] Cannot find Discord channel {channel_id}")
        return

    for offer in offers:
        try:
            message = await channel.send(embed=build_offer_embed(offer))
            try:
                await message.add_reaction(DISMISS_EMOJI)
            except Exception as e:
                print(f"[Jobs] Failed to add dismiss reaction: {e}")
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"[Jobs] Failed to post offer {offer.get('offer_uuid')}: {e}")


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
