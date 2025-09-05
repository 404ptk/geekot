import discord
from discord import app_commands
import json
import os
from typing import List, Optional

GAMES_FILE = "txt/gry.json"

GUILD_ID = 551503797067710504

def load_games():
    if os.path.exists(GAMES_FILE):
        with open(GAMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_games(games):
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=4, ensure_ascii=False)

# Autocomplete function for game names
async def games_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    games_data = load_games()
    choices = []
    
    for i, game in enumerate(games_data, start=1):
        name = game["name"]
        # Add game number and name for easy identification
        display_name = f"{i}. {name}"
        
        # Filter based on user's current input
        if current.lower() in name.lower() or (current.isdigit() and int(current) == i):
            choices.append(app_commands.Choice(name=display_name, value=str(i)))
    
    return choices[:25]  # Discord limits to 25 choices

async def setup_games_commands(client: discord.Client, tree: app_commands.CommandTree):
    """Rejestruje slash commands dla gier"""
    
    # Tworzenie grupy komend dla gier
    gry_group = app_commands.Group(name="gry", description="Komendy związane z grami")
    
    @gry_group.command(name="lista", description="Wyświetla listę wszystkich gier")
    async def gry_lista(interaction: discord.Interaction):
        games_data = load_games()
        if not games_data:
            await interaction.response.send_message(embed=discord.Embed(
                title="Lista gier",
                description="Brak gier na liście.",
                color=discord.Color.blue()
            ))
        else:
            embed = discord.Embed(
                title="Lista gier",
                description="Poniżej znajduje się lista gier, w które chcemy zagrać:",
                color=discord.Color.blue()
            )
            for i, g in enumerate(games_data, start=1):
                name = g["name"]
                desc = g["description"] if g["description"] else "Brak opisu"
                embed.add_field(
                    name=f"{i}. {name}",
                    value=desc,
                    inline=False
                )
            await interaction.response.send_message(embed=embed)

    @gry_group.command(name="dodaj", description="Dodaje nową grę do listy")
    async def gry_dodaj(interaction: discord.Interaction, nazwa_gry: str):
        games_data = load_games()
        games_data.append({"name": nazwa_gry, "description": ""})
        save_games(games_data)
        await interaction.response.send_message(embed=discord.Embed(
            title="Dodano grę",
            description=f"Pomyślnie dodano **{nazwa_gry}** do listy gier.",
            color=discord.Color.blue()
        ))

    @gry_group.command(name="dodajopis", description="Dodaje opis do istniejącej gry")
    @app_commands.autocomplete(wybrana_gra=games_autocomplete)
    async def gry_dodajopis(interaction: discord.Interaction, wybrana_gra: str, opis: str):
        games_data = load_games()
        try:
            # Extract number from selection (format: "1. Game Name")
            index = int(wybrana_gra) - 1
            
            if 0 <= index < len(games_data):
                games_data[index]["description"] = opis
                save_games(games_data)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Dodano opis",
                    description=f"Gra: **{games_data[index]['name']}**\nOpis: {opis}",
                    color=discord.Color.blue()
                ))
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title="Błąd",
                    description="Nieprawidłowy wybór gry!",
                    color=discord.Color.red()
                ))
        except (ValueError, IndexError):
            await interaction.response.send_message(embed=discord.Embed(
                title="Błąd",
                description="Nieprawidłowy wybór gry!",
                color=discord.Color.red()
            ))

    @gry_group.command(name="edytujopis", description="Edytuje opis istniejącej gry")
    @app_commands.autocomplete(wybrana_gra=games_autocomplete)
    async def gry_edytujopis(interaction: discord.Interaction, wybrana_gra: str, nowy_opis: str):
        games_data = load_games()
        try:
            # Extract number from selection (format: "1. Game Name")
            index = int(wybrana_gra) - 1
            
            if 0 <= index < len(games_data):
                games_data[index]["description"] = nowy_opis
                save_games(games_data)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Edytowano opis gry",
                    description=f"Gra: **{games_data[index]['name']}**\nNowy opis: {nowy_opis}",
                    color=discord.Color.blue()
                ))
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title="Błąd",
                    description="Nieprawidłowy wybór gry!",
                    color=discord.Color.red()
                ))
        except (ValueError, IndexError):
            await interaction.response.send_message(embed=discord.Embed(
                title="Błąd",
                description="Nieprawidłowy wybór gry!",
                color=discord.Color.red()
            ))

    @gry_group.command(name="usun", description="Usuwa grę z listy")
    @app_commands.autocomplete(wybrana_gra=games_autocomplete)
    async def gry_usun(interaction: discord.Interaction, wybrana_gra: str):
        games_data = load_games()
        try:
            # Extract number from selection (format: "1. Game Name")
            index = int(wybrana_gra) - 1
            
            if 0 <= index < len(games_data):
                removed_game = games_data.pop(index)
                save_games(games_data)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Usunięto grę",
                    description=f"Z listy usunięto: **{removed_game['name']}**",
                    color=discord.Color.orange()
                ))
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title="Błąd",
                    description="Nieprawidłowy wybór gry!",
                    color=discord.Color.red()
                ))
        except (ValueError, IndexError):
            await interaction.response.send_message(embed=discord.Embed(
                title="Błąd",
                description="Nieprawidłowy wybór gry!",
                color=discord.Color.red()
            ))
            
    @gry_group.command(name="pomoc", description="Wyświetla pomoc dla komend związanych z grami")
    async def gry_pomoc(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pomoc - Komendy związane z grami",
            description="Poniżej znajduje się lista dostępnych komend w kategorii gier:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="/gry lista",
            value="Wyświetla listę wszystkich zapisanych gier wraz z ich opisami.",
            inline=False
        )
        
        embed.add_field(
            name="/gry dodaj [nazwa_gry]",
            value="Dodaje nową grę o podanej nazwie do listy gier.",
            inline=False
        )
        
        embed.add_field(
            name="/gry dodajopis [wybrana_gra] [opis]",
            value="Dodaje opis do istniejącej gry. Można wybrać grę z listy podpowiedzi.",
            inline=False
        )
        
        embed.add_field(
            name="/gry edytujopis [wybrana_gra] [nowy_opis]",
            value="Edytuje opis istniejącej gry. Można wybrać grę z listy podpowiedzi.",
            inline=False
        )
        
        embed.add_field(
            name="/gry usun [wybrana_gra]",
            value="Usuwa grę z listy. Można wybrać grę z listy podpowiedzi.",
            inline=False
        )
        
        embed.add_field(
            name="/gry pomoc",
            value="Wyświetla tę wiadomość z pomocą dotyczącą komend gier.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    # Rejestracja grupy komend tylko dla konkretnego serwera
    tree.add_command(gry_group, guild=discord.Object(id=GUILD_ID))