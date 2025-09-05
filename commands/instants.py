import discord
from discord import app_commands

GUILD_ID = 551503797067710504

INSTANTS = {
    "mirage": {
        "desc": "Instant smokes mid from T spawn (Mirage)",
        "image": "https://cdn.discordapp.com/attachments/809156611167748176/1340791024842309652/mirage_instant_smokes.png?ex=67b3a473&is=67b252f3&hm=addbb5838df74336b88b20d87655daeba80429fad8fa2163721fa0423228e3e0&"
    },
    "anubis": {
        "desc": "Instant smokes mid from CT spawn (Anubis)",
        "image": "https://cdn.discordapp.com/attachments/1301248598108798996/1340782160701030474/image.png?ex=67b39c31&is=67b24ab1&hm=38bd2843da71955749891f1659c81b48c60287c306bf94abdb1adc06a5a2def0&"
    },
    "ancient": {
        "desc": "Instant smokes mid from T spawn (Ancient)",
        "image": "https://cdn.discordapp.com/attachments/809156611167748176/1340790953237151754/ancient_instant_mid_smokes.png?ex=67b3a461&is=67b252e1&hm=d51938f2610cb3ea9c4947000d0bc636d3633f99749b0e193f00d563eb4962e4&",
        "extra_desc": "Instant smokes elbow from CT spawn",
        "extra_image": "https://cdn.discordapp.com/attachments/809156611167748176/1340790762635399198/ancient_instant_elbow_smokes.png?ex=67b3a434&is=67b252b4&hm=5a3b52d428f353172ce9603d9b0d8dfeab40722f211eeae22705bc1f0697bad2&"
    }
}

async def setup_instants_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    @tree.command(
        name="instant",
        description="Wyświetla instanty CS2 dla wybranej mapy",
        guild=discord.Object(id=GUILD_ID)
    )
    @app_commands.describe(mapa="Wybierz mapę")
    @app_commands.choices(
        mapa=[
            app_commands.Choice(name="Mirage", value="mirage"),
            app_commands.Choice(name="Anubis", value="anubis"),
            app_commands.Choice(name="Ancient", value="ancient"),
        ]
    )
    async def instant(interaction: discord.Interaction, mapa: app_commands.Choice[str]):
        key = mapa.value
        data = INSTANTS.get(key)
        if not data:
            await interaction.response.send_message("Nie znaleziono instantów dla tej mapy.", ephemeral=True)
            return

        # Główny embed
        embed = discord.Embed(
            title=data["desc"],
            color=discord.Color.blue()
        )
        embed.set_image(url=data["image"])

        # Jeśli Ancient, dodaj drugi embed z dodatkowym obrazkiem
        if key == "ancient":
            extra_embed = discord.Embed(
                title=data["extra_desc"],
                color=discord.Color.blue()
            )
            extra_embed.set_image(url=data["extra_image"])
            await interaction.response.send_message(embeds=[embed, extra_embed])
        else:
            await interaction.response.send_message(embed=embed)
