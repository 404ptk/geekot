import discord
from discord import app_commands
import json
from pathlib import Path

async def setup_help_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else None
    
    # Helper function to create help embed that will be reused across different commands
    def create_help_embed():
        
        user = client.get_user(1293142451007131740)
        avatar_url = user.display_avatar.url if user else None
        
        embed = discord.Embed(
            title="📜 Dostępne komendy",
            description="Lista komend dostępnych na serwerze:",
            color=discord.Color.blue()
        )
        embed.add_field(name="🎮 **Faceit**", value="Sprawdź statystyki graczy na platformie Faceit:\n"
            "`/faceit [nick]` - Statystyki profilu [nick]\n"
            "`/discordfaceit` - Statystyki discorda na Faceicie\n"
            "`/last [nick]` - Statystyki drużyny gracza w ostatnim meczu", inline=False)
        
        embed.add_field(name="📊 **Tabela Masnego**", value="Śledź i aktualizuj tabelę Masnego na Faceit:\n"
            "`/masny` - Tabela Masnego\n"
            "`/resetmasny` - Resetowanie tabeli", inline=False)
        
        embed.add_field(name="🎭 **Wymówki Masnego**", value="Zarządzaj kolekcją słynnych wymówek Masnego:\n"
            "`/wymowki`", inline=False)
        
        embed.add_field(name="🚀 **Spawn Masnego**", value="Spraw aby Masny był online:\n"
            "`/spawn`", inline=False)
        
        embed.add_field(name="🎥 **Stan streamera**", value="Sprawdź co robi dany streamer:\n"
            "`/stan [kick/twitch] [kanał]`", inline=False)
        
        embed.add_field(name="🎯 **CS2**", value="Przeglądaj dostępne szybkie komendy dla CS2:\n"
            "`/instant`", inline=False)
        
        embed.add_field(name="🔥 **Wyzwania CS2**",
            value="Dodawaj i losuj wyzwania do wykonania w grze CS2:\n"
            "`/wyzwania`", inline=False)
        
        embed.add_field(name="🎮 **Gry do zagrania**", value="*Zarządzaj listą gier, w które chcecie zagrać:*\n"
                        "`/gry`", inline=False)
        
        embed.add_field(name="📝 **Changelog**", value="Najnowsze zmiany w bocie:\n"
                        "`/changelog`", inline=False)
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        embed.set_footer(text="Geekot - Jestem geekiem, największym geekiem 🎮")
        return embed

    # --- Changelog: łatwy do edycji format (grupowanie zmian per data) ---
    project_root = Path(__file__).resolve().parent.parent
    CHANGELOG_FILE = project_root / "txt" / "changelog.json"

    # Domyślny changelog (gdy nie ma pliku txt/changelog.json)
    DEFAULT_CHANGELOG = {
        "2025-09-03": [
            {"title": "Dodano komendę /changelog", "desc": "Wyświetla listę najnowszych zmian w bocie (data -> tytuł/opis)."},
        ]
    }

    def load_changelog():
        try:
            if CHANGELOG_FILE.exists():
                with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Oczekiwany format: { "YYYY-MM-DD": [ {"title": str, "desc": str}, ... ], ... }
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            print(f"[Changelog] Error reading {CHANGELOG_FILE}: {e}")
        return DEFAULT_CHANGELOG

    def create_changelog_embed():
        user = client.get_user(1293142451007131740)
        avatar_url = user.display_avatar.url if user else None

        embed = discord.Embed(
            title="📝 Changelog",
            description="",
            color=discord.Color.orange()
        )

        changelog_map = load_changelog()
        if not changelog_map:
            embed.add_field(name="Brak wpisów", value="Changelog jest pusty.", inline=False)
        else:
            # Pokaż do 7 ostatnich dni zmian; zachowaj kolejność z pliku (gdy ktoś chce manualnie sterować)
            # Jeżeli chcesz wymusić sortowanie po dacie malejąco, odkomentuj linie sortujące poniżej.
            # sorted_items = sorted(changelog_map.items(), key=lambda kv: kv[0], reverse=True)
            items_iterable = list(changelog_map.items())[:7]

            for date_str, items in items_iterable:
                if not isinstance(items, list):
                    continue
                lines = []
                current_len = 0
                for it in items:
                    title = str(it.get("title", "Bez tytułu")).strip()
                    desc = str(it.get("desc", "")).strip()
                    line = f"• {title}"
                    if desc:
                        line += f" — {desc}"
                    # Ogranicz pole embeda do ~1000 znaków na bezpieczeństwo
                    if current_len + len(line) + 1 > 1000:
                        lines.append("• …")
                        break
                    lines.append(line)
                    current_len += len(line) + 1
                value = "\n".join(lines) if lines else "—"
                embed.add_field(name=date_str, value=value, inline=False)

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        embed.set_footer(text="Geekot - Changelog")
        return embed

    # Original pomoc command
    @tree.command(
        name="pomoc",
        description="Wyświetla listę dostępnych komend",
        guild=guild
    )
    async def pomoc(interaction: discord.Interaction):
        await interaction.response.send_message(embed=create_help_embed())
        
    # Add geek as an alias for pomoc
    @tree.command(
        name="geek",
        description="Wyświetla listę dostępnych komend",
        guild=guild
    )
    async def geek(interaction: discord.Interaction):
        await interaction.response.send_message(embed=create_help_embed())
        
    # Add help as an alias for pomoc
    @tree.command(
        name="help",
        description="Wyświetla listę dostępnych komend",
        guild=guild
    )
    async def help(interaction: discord.Interaction):
        await interaction.response.send_message(embed=create_help_embed())

    # Slash command: changelog
    @tree.command(
        name="changelog",
        description="Wyświetla najnowsze zmiany w bocie",
        guild=guild
    )
    async def changelog(interaction: discord.Interaction):
        await interaction.response.send_message(embed=create_changelog_embed())
