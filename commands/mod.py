import discord
import json
import os
from datetime import datetime

GUILD_ID = 551503797067710504
ARCHIVE_CATEGORY_ID = 1360605748186452110
OWNER_ID = 443406275716579348  # Twój discord user ID
CHANNEL_PRIVACY_FILE = "txt/channel_privacy_settings.json"

def load_channel_privacy():
    """Ładuje ustawienia prywatności kanałów"""
    try:
        if os.path.exists(CHANNEL_PRIVACY_FILE):
            with open(CHANNEL_PRIVACY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Błąd przy ładowaniu ustawień prywatności kanałów: {e}")
    return {}


def save_channel_privacy(privacy_data):
    """Zapisuje ustawienia prywatności kanałów"""
    try:
        os.makedirs(os.path.dirname(CHANNEL_PRIVACY_FILE) or '.', exist_ok=True)
        with open(CHANNEL_PRIVACY_FILE, 'w', encoding='utf-8') as f:
            json.dump(privacy_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Błąd przy zapisywaniu ustawień prywatności kanałów: {e}")


def extract_channel_privacy(channel: discord.TextChannel) -> dict:
    """Ekstrahuje ustawienia prywatności z kanału"""
    privacy_settings = {
        "channel_id": channel.id,
        "channel_name": channel.name,
        "saved_at": datetime.now().isoformat(),
        "permissions_overwrites": {},
        "topic": channel.topic,
        "slowmode_delay": channel.slowmode_delay,
        "nsfw": channel.nsfw,
    }
    
    # Zapisz wszystkie permission overwrites
    for target, permissions in channel.overwrites.items():
        target_type = "role" if isinstance(target, discord.Role) else "member"
        target_name = target.name if hasattr(target, "name") else str(target.id)
        
        privacy_settings["permissions_overwrites"][str(target.id)] = {
            "type": target_type,
            "name": target_name,
            "allow": permissions.pair()[0].value,
            "deny": permissions.pair()[1].value,
        }
    
    return privacy_settings

async def setup_mod_commands(client: discord.Client, tree: discord.app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    # --- Zamknij kanał ---
    @tree.command(
        name="zamknij",
        description="Przenosi kanał do archiwum i blokuje pisanie",
        guild=guild
    )
    @discord.app_commands.describe(
        kanal="Kanał do zamknięcia (jeśli nie podasz, zamknie bieżący)"
    )
    async def zamknij(
        interaction: discord.Interaction,
        kanal: discord.TextChannel = None
    ):
        member = interaction.user
        if not any(role.name.lower() == "high tier guard" for role in getattr(member, "roles", [])):
            await interaction.response.send_message(
                "Nie masz wystarczających uprawnień do wykonania tej komendy.",
                ephemeral=True
            )
            return

        channel = kanal or interaction.channel
        category = discord.utils.get(interaction.guild.categories, id=ARCHIVE_CATEGORY_ID)
        if category is None:
            await interaction.response.send_message(
                f"Nie znaleziono kategorii o ID {ARCHIVE_CATEGORY_ID}.",
                ephemeral=True
            )
            return

        # Zapisz ustawienia prywatności kanału
        privacy_data = load_channel_privacy()
        channel_settings = extract_channel_privacy(channel)
        privacy_data[str(channel.id)] = channel_settings
        save_channel_privacy(privacy_data)

        await channel.edit(category=category)
        await channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(
            f"Kanał {channel.mention} został przeniesiony do kategorii **{category.name}** i zablokowano możliwość pisania.\n✅ Ustawienia prywatności kanału zostały zapisane."
        )

    # --- Czyszczenie wiadomości ---
    @tree.command(
        name="czysc",
        description="Usuwa ostatnie wiadomości na bieżącym kanale",
        guild=guild,
    )
    @discord.app_commands.describe(
        liczba="Ile wiadomości usunąć (1-100)",
        uzytkownik="Usuń ostatnie wiadomości tego użytkownika (opcjonalnie)",
    )
    async def czysc(
        interaction: discord.Interaction,
        liczba: discord.app_commands.Range[int, 1, 100],
        uzytkownik: discord.Member = None,
    ):
        member = interaction.user
        if not any(role.name.lower() == "high tier guard" for role in getattr(member, "roles", [])):
            await interaction.response.send_message(
                "Nie masz wystarczających uprawnień do wykonania tej komendy.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Ta komenda działa tylko na kanałach tekstowych.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message(
                "Bot nie ma uprawnienia do zarządzania wiadomościami na tym kanale.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        reason = f"Czyszczenie przez {interaction.user} ({interaction.user.id})"
        try:
            if uzytkownik:
                matched = {"count": 0}

                def check(message: discord.Message) -> bool:
                    if message.author.id != uzytkownik.id:
                        return False
                    matched["count"] += 1
                    return matched["count"] <= liczba

                deleted = await channel.purge(limit=1000, check=check, reason=reason)
                await interaction.followup.send(
                    f"Usunięto **{len(deleted)}** wiadomości użytkownika {uzytkownik.mention} na {channel.mention}.",
                    ephemeral=True,
                )
            else:
                deleted = await channel.purge(limit=liczba, reason=reason)
                await interaction.followup.send(
                    f"Usunięto **{len(deleted)}** ostatnich wiadomości na {channel.mention}.",
                    ephemeral=True,
                )
        except discord.Forbidden:
            await interaction.followup.send(
                "Nie udało się usunąć wiadomości — brak uprawnień.",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"Nie udało się usunąć wiadomości: {e}",
                ephemeral=True,
            )

    # --- Synchronizacja globalna ---
    @tree.command(
        name="sync",
        description="Synchronizuje komendy slash globalnie",
        guild=guild
    )
    async def sync(interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Nie masz uprawnień do synchronizacji komend.", ephemeral=True)
            return
        try:
            synced = await client.tree.sync()
            await interaction.response.send_message(f"✅ Zsynchronizowano {len(synced)} komend slash globalnie.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd synchronizacji: {e}", ephemeral=True)

    # --- Synchronizacja dla serwera ---
    @tree.command(
        name="guildsync",
        description="Synchronizuje komendy slash tylko dla tego serwera",
        guild=guild
    )
    async def guildsync(interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Nie masz uprawnień do synchronizacji komend.", ephemeral=True)
            return
        try:
            synced = await client.tree.sync(guild=discord.Object(id=interaction.guild.id))
            await interaction.response.send_message(f"✅ Zsynchronizowano {len(synced)} komend slash dla tego serwera.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd synchronizacji: {e}", ephemeral=True)

    # --- Czyszczenie komend na serwerze ---
    @tree.command(
        name="clearcmds",
        description="Czyści wszystkie komendy slash z tego serwera",
        guild=guild
    )
    async def clearcmds(interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Nie masz uprawnień do tej operacji.", ephemeral=True)
            return
        client.tree.clear_commands(guild=discord.Object(id=interaction.guild.id))
        await client.tree.sync(guild=discord.Object(id=interaction.guild.id))
        await interaction.response.send_message("Wyczyszczono komendy slash dla tego serwera.")

    # --- Lista globalnych komend slash ---
    @tree.command(
        name="slashlist",
        description="Wyświetla listę globalnych komend slash",
        guild=guild
    )
    async def slashlist(interaction: discord.Interaction):
        cmds = client.tree.get_commands()
        if cmds:
            cmd_names = "\n".join(f"- {cmd.name}" for cmd in cmds)
            await interaction.response.send_message(f"**Globalne komendy slash:**\n{cmd_names}")
        else:
            await interaction.response.send_message("Brak zarejestrowanych globalnych komend slash.")

    # --- Lista komend slash na tym serwerze ---
    @tree.command(
        name="gslashlist",
        description="Wyświetla listę komend slash na tym serwerze",
        guild=guild
    )
    async def gslashlist(interaction: discord.Interaction):
        cmds = client.tree.get_commands(guild=discord.Object(id=interaction.guild.id))
        if cmds:
            cmd_names = "\n".join(f"- {cmd.name}" for cmd in cmds)
            await interaction.response.send_message(f"**Komendy slash na tym serwerze:**\n{cmd_names}")
        else:
            await interaction.response.send_message("Brak zarejestrowanych komend slash na tym serwerze.")

    # --- Czyszczenie globalnych komend slash ---
    @tree.command(
        name="clearglobalcmds",
        description="Czyści wszystkie globalne komendy slash",
        guild=guild
    )
    async def clearglobalcmds(interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Nie masz uprawnień do tej operacji.", ephemeral=True)
            return
        try:
            client.tree.clear_commands(guild=None)
            synced = await client.tree.sync()
            await interaction.response.send_message("✅ Usunięto wszystkie globalne komendy slash.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd podczas czyszczenia globalnych komend: {e}", ephemeral=True)
