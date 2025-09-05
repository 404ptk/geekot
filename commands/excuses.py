import discord
from discord import app_commands
import os
import random
from typing import List

WYMOWKI_FILE = "txt/wymowki.txt"

GUILD_ID = 551503797067710504

def load_wymowki():
    if os.path.exists(WYMOWKI_FILE):
        with open(WYMOWKI_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]
    return []

def save_wymowki(wymowki):
    with open(WYMOWKI_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(wymowki))

# Autocomplete function for wymówki
async def wymowki_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    wymowki = load_wymowki()
    choices = []
    
    for i, wymowka in enumerate(wymowki, start=1):
        # Skróć wymówkę jeśli jest za długa dla wyświetlania
        display_text = wymowka[:50] + "..." if len(wymowka) > 50 else wymowka
        display_name = f"{i}. {display_text}"
        
        # Filtruj na podstawie wpisanego tekstu
        if (current.lower() in wymowka.lower() or 
            (current.isdigit() and int(current) == i)):
            choices.append(app_commands.Choice(name=display_name, value=str(i)))
    
    return choices[:25]  # Discord limits to 25 choices

async def setup_excuses_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    # Tworzenie grupy komend dla wymówek
    wymowki_group = app_commands.Group(name="wymowki", description="Komendy związane z wymówkami Masnego")
    
    @wymowki_group.command(name="losuj", description="Losuje wymówkę Masnego")
    async def wymowki_losuj(interaction: discord.Interaction):
        wymowki = load_wymowki()
        if not wymowki:
            await interaction.response.send_message(embed=discord.Embed(
                title="🎭 Wymówka Masnego",
                description="Brak zapisanych wymówek.",
                color=discord.Color.red()
            ))
            return
        wymowka = random.choice(wymowki)
        embed = discord.Embed(
            title="🎭 Wymówka Masnego",
            description=wymowka,
            color=discord.Color.dark_magenta()
        )
        await interaction.response.send_message(embed=embed)

    @wymowki_group.command(name="dodaj", description="Dodaje nową wymówkę")
    @app_commands.describe(tresc="Treść nowej wymówki")
    async def wymowki_dodaj(interaction: discord.Interaction, tresc: str):
        wymowki = load_wymowki()
        nowa = tresc.strip()
        wymowki.append(nowa)
        save_wymowki(wymowki)
        embed = discord.Embed(
            title="✅ Dodano nową wymówkę",
            description=nowa,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @wymowki_group.command(name="lista", description="Wyświetla listę wszystkich wymówek")
    async def wymowki_lista(interaction: discord.Interaction):
        wymowki = load_wymowki()
        if not wymowki:
            embed = discord.Embed(
                title="🎭 Lista wymówek Masnego",
                description="Brak zapisanych wymówek. Dodaj jedną za pomocą `/wymowki dodaj`!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Zapisz wymówki Masnego!")
            await interaction.response.send_message(embed=embed)
        else:
            wymowki_list = "\n".join(f"{i + 1}. {wymowka}" for i, wymowka in enumerate(wymowki))
            embed = discord.Embed(
                title="🎭 Lista wymówek Masnego",
                description=f"Oto wszystkie zapisane wymówki:\n{wymowki_list}",
                color=discord.Color.purple()
            )
            embed.set_footer(text=f"Liczba wymówek: {len(wymowki)} | Losuj jedną za pomocą `/wymowki losuj`")
            await interaction.response.send_message(embed=embed)

    @wymowki_group.command(name="usun", description="Usuwa wymówkę z listy")
    @app_commands.autocomplete(wybrana_wymowka=wymowki_autocomplete)
    async def wymowki_usun(interaction: discord.Interaction, wybrana_wymowka: str):
        wymowki = load_wymowki()
        try:
            # Extract number from selection (format: "1. Wymówka text...")
            index = int(wybrana_wymowka) - 1
            
            if 0 <= index < len(wymowki):
                removed = wymowki.pop(index)
                save_wymowki(wymowki)
                embed = discord.Embed(
                    title="🗑️ Usunięto wymówkę",
                    description=removed,
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Sprawdź listę za pomocą `/wymowki lista`")
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title="❌ Błąd",
                    description="Nieprawidłowy wybór wymówki!",
                    color=discord.Color.red()
                ))
        except (ValueError, IndexError):
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Błąd",
                description="Nieprawidłowy wybór wymówki!",
                color=discord.Color.red()
            ))
            
    @wymowki_group.command(name="pomoc", description="Wyświetla pomoc dla komend związanych z wymówkami")
    async def wymowki_pomoc(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pomoc - Komendy związane z wymówkami",
            description="Poniżej znajduje się lista dostępnych komend w kategorii wymówek:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="/wymowki lista",
            value="Wyświetla listę wszystkich zapisanych wymówek.",
            inline=False
        )
        
        embed.add_field(
            name="/wymowki dodaj [tresc]",
            value="Dodaje nową wymówkę o podanej treści.",
            inline=False
        )
        
        embed.add_field(
            name="/wymowki usun [wybrana_wymowka]",
            value="Usuwa wymówkę z listy. Można wybrać wymówkę z listy podpowiedzi.",
            inline=False
        )
        
        embed.add_field(
            name="/wymowki losuj",
            value="Wyświetla losową wymówkę z listy.",
            inline=False
        )
        
        embed.add_field(
            name="/wymowki pomoc",
            value="Wyświetla tę wiadomość z pomocą dotyczącą komend wymówek.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    # Rejestracja grupy komend tylko dla konkretnego serwera
    tree.add_command(wymowki_group, guild=discord.Object(id=GUILD_ID))

