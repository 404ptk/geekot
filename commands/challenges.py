import discord
from discord import app_commands
import os
import random
from typing import List

GUILD_ID = 551503797067710504

CHALLENGES_FILE = "txt/challenges.txt"
challenges = []

def save_challenges():
    with open(CHALLENGES_FILE, "w", encoding="utf-8") as file:
        for challenge in challenges:
            file.write(challenge + "\n")

def load_challenges():
    challenges.clear()
    if os.path.exists(CHALLENGES_FILE):
        with open(CHALLENGES_FILE, "r", encoding="utf-8") as file:
            for line in file:
                challenges.append(line.strip())
        print("challenges.txt loaded.")
    else:
        default_challenges = [
            "Zagraj rundę tylko z Deagle",
            "Wygraj mecz bez kupowania granatów",
            "Użyj tylko noża w jednej rundzie",
            "Zabij 3 przeciwników z AWP w jednym meczu"
        ]
        print("Error in loading challenges.txt - Creating new file.")
        challenges.extend(default_challenges)
        save_challenges()

# Załaduj przy starcie
load_challenges()

# Autocomplete function for challenges
async def challenges_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    choices = []
    
    for i, challenge in enumerate(challenges, start=1):
        # Skróć wyzwanie, jeśli jest za długie dla wyświetlania
        display_text = challenge[:50] + "..." if len(challenge) > 50 else challenge
        display_name = f"{i}. {display_text}"
        
        # Filtruj na podstawie wpisanego tekstu
        if (current.lower() in challenge.lower() or 
            (current.isdigit() and int(current) == i)):
            choices.append(app_commands.Choice(name=display_name, value=str(i)))
    
    return choices[:25]  # Discord limits to 25 choices

async def setup_challenges_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)
    
    # Tworzenie grupy komend dla wyzwań
    wyzwania_group = app_commands.Group(name="wyzwania", description="Komendy związane z wyzwaniami CS2")
    
    @wyzwania_group.command(name="losuj", description="Losuje wyzwanie CS2")
    async def wyzwania_losuj(interaction: discord.Interaction):
        if not challenges:
            embed = discord.Embed(
                title="📋 Lista wyzwań CS2",
                description="Brak zapisanych wyzwań. Dodaj jedno za pomocą `/wyzwania dodaj`!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Stwórz swoje wyzwanie!")
            await interaction.response.send_message(embed=embed)
        else:
            challenge = random.choice(challenges)
            embed = discord.Embed(
                title="🎯 Twoje wyzwanie CS2",
                description=f"**{challenge}**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Dodaj własne wyzwanie za pomocą `/wyzwania dodaj`\nPowodzenia!")
            await interaction.response.send_message(embed=embed)

    @wyzwania_group.command(name="dodaj", description="Dodaje nowe wyzwanie do listy")
    @app_commands.describe(tresc="Treść nowego wyzwania")
    async def wyzwania_dodaj(interaction: discord.Interaction, tresc: str):
        new_challenge = tresc.strip()
        challenges.append(new_challenge)
        save_challenges()
        embed = discord.Embed(
            title="✅ Nowe wyzwanie dodane!",
            description=f"Dodałeś: **{new_challenge}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Spróbuj je wylosować za pomocą `/wyzwania losuj`")
        print(f"Added challenge '{new_challenge}' to list.")
        await interaction.response.send_message(embed=embed)

    @wyzwania_group.command(name="lista", description="Wyświetla listę wszystkich wyzwań CS2")
    async def wyzwania_lista(interaction: discord.Interaction):
        if not challenges:
            await interaction.response.send_message("Brak zapisanych wyzwań. Dodaj jedno za pomocą `/wyzwania dodaj`!")
        else:
            challenges_list = "\n".join(f"{i + 1}. {challenge}" for i, challenge in enumerate(challenges))
            embed = discord.Embed(
                title="📋 Lista wyzwań CS2",
                description=f"Oto dostępne wyzwania:\n{challenges_list}",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Użyj `/wyzwania losuj`, aby wylosować jedno z nich!")
            await interaction.response.send_message(embed=embed)

    @wyzwania_group.command(name="usun", description="Usuwa wyzwanie z listy")
    @app_commands.autocomplete(wybrane_wyzwanie=challenges_autocomplete)
    async def wyzwania_usun(interaction: discord.Interaction, wybrane_wyzwanie: str):
        try:
            # Extract number from selection (format: "1. Challenge text...")
            index = int(wybrane_wyzwanie) - 1
            
            if 0 <= index < len(challenges):
                removed_challenge = challenges.pop(index)
                save_challenges()
                embed = discord.Embed(
                    title="✅ Wyzwanie usunięte",
                    description=f"Usunięto: **{removed_challenge}**",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Sprawdź listę za pomocą `/wyzwania lista`")
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title="⚠️ Błąd",
                    description="Nieprawidłowy wybór wyzwania!",
                    color=discord.Color.red()
                ))
        except (ValueError, IndexError):
            await interaction.response.send_message(embed=discord.Embed(
                title="⚠️ Błąd",
                description="Nieprawidłowy wybór wyzwania!",
                color=discord.Color.red()
            ))
            
    @wyzwania_group.command(name="pomoc", description="Wyświetla pomoc dla komend związanych z wyzwaniami")
    async def wyzwania_pomoc(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pomoc - Komendy związane z wyzwaniami CS2",
            description="Poniżej znajduje się lista dostępnych komend w kategorii wyzwań:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="/wyzwania lista",
            value="Wyświetla listę wszystkich zapisanych wyzwań.",
            inline=False
        )
        
        embed.add_field(
            name="/wyzwania dodaj [tresc]",
            value="Dodaje nowe wyzwanie o podanej treści.",
            inline=False
        )
        
        embed.add_field(
            name="/wyzwania usun [wybrane_wyzwanie]",
            value="Usuwa wyzwanie z listy. Można wybrać wyzwanie z listy podpowiedzi.",
            inline=False
        )
        
        embed.add_field(
            name="/wyzwania losuj",
            value="Wyświetla losowe wyzwanie z listy.",
            inline=False
        )
        
        embed.add_field(
            name="/wyzwania pomoc",
            value="Wyświetla tę wiadomość z pomocą dotyczącą komend wyzwań.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    # Rejestracja grupy komend
    tree.add_command(wyzwania_group, guild=guild)
