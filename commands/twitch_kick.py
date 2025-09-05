import discord
from discord import app_commands

from twitch_utils import get_twitch_stream_data
from kick_utils import get_kick_stream_data

GUILD_ID = 551503797067710504

async def setup_twitch_kick_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    @tree.command(
        name="stan",
        description="Sprawdza stan streamera na Twitch lub Kick",
        guild=guild
    )
    @app_commands.describe(
        platforma="Wybierz platformę: twitch lub kick",
        nazwa="Nazwa użytkownika na wybranej platformie"
    )
    @app_commands.choices(
        platforma=[
            app_commands.Choice(name="Twitch", value="twitch"),
            app_commands.Choice(name="Kick", value="kick"),
        ]
    )
    async def stan(
        interaction: discord.Interaction,
        platforma: app_commands.Choice[str],
        nazwa: str
    ):
        platform = platforma.value.lower()
        username = nazwa

        if platform == "twitch":
            stream_data = get_twitch_stream_data(username)
            embed = discord.Embed(
                title=f"Stan streama Twitch: {username}",
                color=discord.Color.purple()
            )
            if stream_data is None:
                await interaction.response.send_message(
                    f"Nie udało się pobrać danych z Twitcha dla użytkownika {username}.",
                    ephemeral=True
                )
                return

            if stream_data['live']:
                viewer_line = f"\n👥 Widzowie: {stream_data.get('viewer_count', 'brak danych')}"
                embed.description = f"**{username} jest na żywo!**\n*{stream_data['title']}*{viewer_line}"
                embed.set_image(url=stream_data['thumbnail_url'])
            else:
                embed.description = f"**{username} jest offline.**"
                if stream_data['thumbnail_url']:
                    embed.set_image(url=stream_data['thumbnail_url'])
                else:
                    embed.set_image(url="https://static-cdn.jtvnw.net/ttv-static/404_preview-1280x720.jpg")
            embed.add_field(
                name="Kanał Twitch",
                value=f"[{username}](https://twitch.tv/{username})",
                inline=False
            )
            await interaction.response.send_message(embed=embed)

        elif platform == "kick":
            kick_data = get_kick_stream_data(username)
            embed = discord.Embed(
                title=f"Stan streama Kick: {username}",
                color=discord.Color.green()
            )
            if not kick_data:
                await interaction.response.send_message(
                    f"Nie można pobrać danych Kick dla kanału '{username}'.",
                    ephemeral=True
                )
                return

            if kick_data['live']:
                viewer_line = f"👥 Widzowie: {kick_data['viewer_count']}" if kick_data['viewer_count'] is not None else ""
                embed.description = (
                    f"**{username}** jest właśnie LIVE!\n"
                    f"*{kick_data['title']}*\n"
                    f"\n{viewer_line}"
                )
                if kick_data['thumbnail_url']:
                    embed.set_image(url=kick_data['thumbnail_url'])
            else:
                embed.description = f"**{username}** jest offline.\nTytuł: {kick_data['title']}"
            embed.add_field(
                name="Kanał Kick",
                value=f"[{username}](https://kick.com/{username})",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"Nierozpoznana platforma `{platform}`. Wybierz `twitch` lub `kick`.",
                ephemeral=True
            )
