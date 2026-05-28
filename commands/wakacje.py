import discord
from discord import app_commands
import json
import os
import uuid
from typing import List, Optional
from startup_logger import record_startup_step

WAKACJE_FILE = "txt/wakacje.json"
GUILD_ID = 551503797067710504


def load_wakacje(startup_label=None):
    """Ładuje listę wakacji z pliku JSON"""
    if os.path.exists(WAKACJE_FILE):
        with open(WAKACJE_FILE, "r", encoding="utf-8") as f:
            wakacje = json.load(f)
        if startup_label:
            record_startup_step(startup_label, True, WAKACJE_FILE)
        return wakacje
    
    if startup_label:
        record_startup_step(startup_label, False, f"{WAKACJE_FILE} not found")
    return []


def save_wakacje(wakacje):
    """Zapisuje listę wakacji do pliku JSON"""
    try:
        os.makedirs(os.path.dirname(WAKACJE_FILE), exist_ok=True)
        with open(WAKACJE_FILE, "w", encoding="utf-8") as f:
            json.dump(wakacje, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving wakacje: {e}")


def truncate_text(text: str, max_length: int = 30) -> str:
    """Skraca tekst do maksymalnej długości"""
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text


async def wakacje_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    """Autocomplete dla krótkich opisów wakacji"""
    wakacje = load_wakacje()
    choices = []
    
    for wakacja in wakacje:
        krotki_opis = wakacja["krotki_opis"]
        if current.lower() in krotki_opis.lower():
            choices.append(app_commands.Choice(name=krotki_opis, value=krotki_opis))
    
    return choices[:25]  # Discord limit


async def setup_wakacje_commands(client: discord.Client, tree: app_commands.CommandTree):
    """Rejestruje slash commands dla wakacji"""
    
    wakacje_group = app_commands.Group(name="wakacje", description="Komendy do zarządzania wakacjami")
    
    @wakacje_group.command(
        name="lista",
        description="Wyświetla listę wszystkich dostępnych opcji wakacji"
    )
    async def wakacje_lista(interaction: discord.Interaction):
        """Wyświetla listę wakacji w ładnym formacie"""
        wakacje = load_wakacje()
        
        if not wakacje:
            embed = discord.Embed(
                title="📋 Pomysły na wakację",
                description="Brak opcji wakacji. Dodaj nową używając `/wakacje dodaj`",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Pomysły na wakację",
            description=f"Dostępnych opcji: {len(wakacje)}",
            color=discord.Color.blue()
        )
        
        for i, wakacja in enumerate(wakacje, start=1):
            krotki_opis = wakacja["krotki_opis"]
            kraj = wakacja["kraj"]
            data = wakacja["data"]
            kwota = wakacja["kwota"]
            link = wakacja.get("link", "")
            
            # Tworzymy wartość z linkowanym tekstem jeśli link istnieje
            if link:
                value = f"🌍 **{kraj}** | 📅 {data} | 💰 {kwota}zł\n[Link]({link})"
            else:
                value = f"🌍 **{kraj}** | 📅 {data} | 💰 {kwota}"
            
            embed.add_field(
                name=f"{i}. {truncate_text(krotki_opis, 25)}",
                value=value,
                inline=False
            )
        
        embed.set_footer(text="💡 Użyj /wakacje pokaz [nazwa] aby zobaczyć pełne szczegóły")
        await interaction.response.send_message(embed=embed)
    
    @wakacje_group.command(
        name="pokaz",
        description="Wyświetla pełne szczegóły konkretnej opcji wakacji"
    )
    @app_commands.autocomplete(krotki_opis=wakacje_autocomplete)
    async def wakacje_pokaz(interaction: discord.Interaction, krotki_opis: str):
        """Wyświetla szczegóły konkretnej wakacji"""
        wakacje = load_wakacje()
        
        wakacja = next((w for w in wakacje if w["krotki_opis"].lower() == krotki_opis.lower()), None)
        
        if not wakacja:
            embed = discord.Embed(
                title="❌ Nie znaleziono",
                description=f"Opcja wakacji '{krotki_opis}' nie istnieje.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🏖️ {wakacja['krotki_opis']}",
            description=wakacja["opis"],
            color=discord.Color.green()
        )
        
        embed.add_field(name="🌍 Kraj", value=wakacja["kraj"], inline=True)
        embed.add_field(name="📅 Data", value=wakacja["data"], inline=True)
        embed.add_field(name="💰 Kwota", value=wakacja["kwota"], inline=True)
        
        if wakacja.get("link"):
            embed.add_field(
                name="🔗 Link",
                value=f"[Otwórz]({wakacja['link']})",
                inline=False
            )
        
        embed.set_footer(text="💼 Szczegóły oferty")
        await interaction.response.send_message(embed=embed)
    
    @wakacje_group.command(
        name="dodaj",
        description="Dodaje nową opcję wakacji"
    )
    async def wakacje_dodaj(
        interaction: discord.Interaction,
        krotki_opis: str,
        kraj: str,
        data: str,
        kwota: str,
        opis: str,
        link: str = None
    ):
        """Dodaje nową opcję wakacji"""
        
        # Walidacja długości krótki opisów
        if len(krotki_opis) > 30:
            embed = discord.Embed(
                title="❌ Błąd",
                description="Krótki opis nie może mieć więcej niż 30 znaków!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        wakacje = load_wakacje()
        
        # Sprawdzenie czy taka wakacja już istnieje
        if any(w["krotki_opis"].lower() == krotki_opis.lower() for w in wakacje):
            embed = discord.Embed(
                title="❌ Błąd",
                description=f"Wakacja o nazwie '{krotki_opis}' już istnieje!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Dodawanie nowej wakacji
        nowa_wakacja = {
            "id": str(uuid.uuid4()),
            "krotki_opis": krotki_opis,
            "kraj": kraj,
            "data": data,
            "kwota": kwota,
            "opis": opis
        }
        
        if link:
            nowa_wakacja["link"] = link
        
        wakacje.append(nowa_wakacja)
        save_wakacje(wakacje)
        
        embed = discord.Embed(
            title="✅ Sukces",
            description=f"Dodano nową opcję wakacji: **{krotki_opis}**",
            color=discord.Color.green()
        )
        
        embed.add_field(name="🌍 Kraj", value=kraj, inline=True)
        embed.add_field(name="📅 Data", value=data, inline=True)
        embed.add_field(name="💰 Kwota", value=kwota, inline=True)
        embed.add_field(name="📝 Opis", value=truncate_text(opis, 50), inline=False)
        
        if link:
            embed.add_field(name="🔗 Link", value=f"[Otwórz]({link})", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @wakacje_group.command(
        name="usun",
        description="Usuwa opcję wakacji z listy"
    )
    @app_commands.autocomplete(krotki_opis=wakacje_autocomplete)
    async def wakacje_usun(interaction: discord.Interaction, krotki_opis: str):
        """Usuwa wakację z listy"""
        wakacje = load_wakacje()
        
        wakacja = next((w for w in wakacje if w["krotki_opis"].lower() == krotki_opis.lower()), None)
        
        if not wakacja:
            embed = discord.Embed(
                title="❌ Nie znaleziono",
                description=f"Opcja wakacji '{krotki_opis}' nie istnieje.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        wakacje.remove(wakacja)
        save_wakacje(wakacje)
        
        embed = discord.Embed(
            title="✅ Sukces",
            description=f"Usunięto opcję wakacji: **{krotki_opis}**",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Pozostało {len(wakacje)} opcji na liście")
        
        await interaction.response.send_message(embed=embed)
    
    tree.add_command(wakacje_group, guild=discord.Object(id=GUILD_ID))
