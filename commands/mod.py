import discord

GUILD_ID = 551503797067710504
ARCHIVE_CATEGORY_ID = 1360605748186452110
OWNER_ID = 443406275716579348  # Twój discord user ID

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

        await channel.edit(category=category)
        await channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(
            f"Kanał {channel.mention} został przeniesiony do kategorii **{category.name}** i zablokowano możliwość pisania."
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

    print("Slash komendy administracyjne zarejestrowane w mod.py")
