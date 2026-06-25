import discord


async def get_discord_channel(client: discord.Client, channel_id: int):
    channel = client.get_channel(channel_id)
    if channel:
        return channel
    try:
        return await client.fetch_channel(channel_id)
    except Exception:
        return None
