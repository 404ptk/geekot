import discord
from datetime import date
from discord import app_commands
import os

REFERENCE_DATE_FILE = "txt/days_reference.txt"

GUILD_ID = 551503797067710504

def load_reference_date():
    """
    Wczytuje datę odniesienia z pliku.
    Jeżeli plik nie istnieje, tworzy go z domyślną datą 02.11.2024.
    """
    if not os.path.exists(REFERENCE_DATE_FILE):
        with open(REFERENCE_DATE_FILE, 'w', encoding="utf-8") as f:
            f.write("2024-11-02")
            print("Error in loading days_reference.txt - Creating a new file.")
        return date(2024, 11, 2)

    else:
        with open(REFERENCE_DATE_FILE, 'r', encoding="utf-8") as f:
            date_str = f.read().strip()
            year, month, day = date_str.split("-")
            print("days_reference.txt loaded.")
            return date(int(year), int(month), int(day))

def save_reference_date(d: date):
    with open(REFERENCE_DATE_FILE, 'w', encoding="utf-8") as f:
        f.write(d.isoformat())

async def setup_minecraft_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else None

    @tree.command(
        name="ile",
        description="Ile dni minęło od ostatniego serwera minecraft?",
        guild=discord.Object(id=GUILD_ID)
    )
    async def ile(interaction: discord.Interaction):
        ref_date = load_reference_date()
        today = date.today()
        diff = (today - ref_date).days

        embed = discord.Embed(
            title="Ile dni minęło od ostatniego serwera minecraft?",
            color=discord.Color.blue()
        )

        if diff < 0:
            embed.add_field(
                name="Wynik",
                value=(
                    f"Ustawiona data ({ref_date}) jest w przyszłości!\n"
                    f"Do **{ref_date}** pozostało jeszcze **{abs(diff)}** dni."
                ),
                inline=False
            )
        else:
            embed.add_field(
                name=f"*{diff} dni*... 😢",
                value="",
                inline=False
            )

        embed.set_image(
            url="https://media.discordapp.net/attachments/607581853880418366/1302050384184999978/image.png?ex=67c6e2aa&is=67c5912a&hm=a8b52b3437f22136b0436de0c4da302ed0ef8800f64757598c0fd0da3cd639c0&=&format=webp&quality=lossless&width=1437&height=772"
        )

        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="ilereset",
        description="Resetuje licznik dni od ostatniego serwera minecraft",
        guild=discord.Object(id=GUILD_ID)
    )
    async def ilereset(interaction: discord.Interaction):
        now = date.today()
        save_reference_date(now)

        embed = discord.Embed(
            title="Zresetowano odliczanie",
            description=(
                f"Od teraz liczba dni będzie naliczana od dzisiejszej daty:\n"
                f"**{now.isoformat()}**"
            ),
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed)

    print("Minecraft slash commands registered.")
