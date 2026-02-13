import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import time
import logging
from datetime import timedelta

STATS_FILE = "txt/server_stats.json"
IGNORED_CHANNEL_ID = 710042604720488520
active_voice_sessions = {}

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load stats: {e}")
        return {}

def save_stats(stats):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save stats: {e}")

def update_message_count(user_id):
    stats = load_stats()
    user_id_str = str(user_id)
    if user_id_str not in stats:
        stats[user_id_str] = {"messages": 0, "voice_time": 0}
    
    stats[user_id_str]["messages"] = stats[user_id_str].get("messages", 0) + 1
    save_stats(stats)

def update_voice_time(user_id, duration):
    stats = load_stats()
    user_id_str = str(user_id)
    if user_id_str not in stats:
        stats[user_id_str] = {"messages": 0, "voice_time": 0}
    
    current_time = stats[user_id_str].get("voice_time", 0)
    stats[user_id_str]["voice_time"] = current_time + duration
    save_stats(stats)

def format_duration(seconds):
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "0m"

@tasks.loop(minutes=2)
async def commit_voice_stats():
    global active_voice_sessions
    if not active_voice_sessions:
        return
        
    stats = load_stats()
    now = time.time()
    changed = False
    
    for user_id, start_time in list(active_voice_sessions.items()):
        duration = now - start_time
        # Zapisz tylko jeśli minął jakiś sensowny czas (np. > 1s)
        if duration > 1:
            uid_str = str(user_id)
            if uid_str not in stats:
                stats[uid_str] = {"messages": 0, "voice_time": 0}
            
            stats[uid_str]["voice_time"] = stats[uid_str].get("voice_time", 0) + duration
            # Zaktualizuj czas startu na "teraz", żeby nie liczyć podwójnie
            active_voice_sessions[user_id] = now
            changed = True
            
    if changed:
        save_stats(stats)

async def setup_fun_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int):
    guild_obj = discord.Object(id=guild_id)

    # --- Listeners ---
    async def listener_on_message(message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id == IGNORED_CHANNEL_ID:
            return
        
        # Ignorowanie komend (zaczynających się od / lub ! s)
        if message.content.startswith(('!', '/')):
            return

        update_message_count(message.author.id)

    async def listener_on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        user_id = member.id
        now = time.time()

        # Użytkownik dołączył do kanału (nie był wcześniej, a teraz jest)
        if before.channel is None and after.channel is not None:
            active_voice_sessions[user_id] = now
        
        # Użytkownik wyszedł z kanału
        elif before.channel is not None and after.channel is None:
            if user_id in active_voice_sessions:
                start_time = active_voice_sessions.pop(user_id)
                duration = now - start_time
                update_voice_time(user_id, duration)
        
        # Użytkownik przełączył kanał (był i jest, ale inny kanał) - traktujemy jako ciągłość, chyba że chcemy być super precyzyjni
        # Jeśli po prostu przełącza, sesja trwa dalej. 
        # Ale jeśli np. robi stream on/off, to też triggeruje update.
        # Weryfikacja czy w ogóle jest w kanale:
        if before.channel is not None and after.channel is None:
             # Już obsłużone wyżej jako wyjście
             pass

    # Rejestracja listenerów
    client.add_listener(listener_on_message, 'on_message')
    client.add_listener(listener_on_voice_state_update, 'on_voice_state_update')
    
    # Uruchomienie zadania w tle do zapisywania statystyk
    if not commit_voice_stats.is_running():
        commit_voice_stats.start()

    # Przeskanowanie obecnych użytkowników na głosowych przy starcie bota (resecie modułu)
    # Wymaga obiektu gildii, pobieramy go z clienta
    guild = client.get_guild(guild_id)
    if guild:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot:
                    active_voice_sessions[member.id] = time.time()

    # --- Komendy ---
    @tree.command(name="ranking", description="Wyświetla ranking aktywności serwera", guild=guild_obj)
    async def ranking(interaction: discord.Interaction):
        stats = load_stats()
        
        # Zbieramy wszystkich unikalnych użytkowników (z pliku i z aktywnych sesji)
        all_user_ids = set(stats.keys())
        for uid in active_voice_sessions.keys():
            all_user_ids.add(str(uid))

        if not all_user_ids:
            await interaction.response.send_message("Brak danych w rankingu.", ephemeral=True)
            return

        # Przetwarzanie danych
        # Voice ranking
        voice_data = []
        msg_data = []
        
        for uid_str in all_user_ids:
            # Dane z pliku
            user_stat = stats.get(uid_str, {})
            v_time = user_stat.get("voice_time", 0)
            m_count = user_stat.get("messages", 0)
            
            # Jeśli user jest aktualnie na kanale, dolicz mu czas sesji "w locie"
            uid_int = int(uid_str)
            if uid_int in active_voice_sessions:
                current_session_duration = time.time() - active_voice_sessions[uid_int]
                v_time += current_session_duration

            if v_time > 0:
                voice_data.append((uid_str, v_time))
            if m_count > 0:
                msg_data.append((uid_str, m_count))

        # Sortowanie
        voice_data.sort(key=lambda x: x[1], reverse=True)
        msg_data.sort(key=lambda x: x[1], reverse=True)
        
        # Top 5
        top_voice = voice_data[:5]
        top_msg = msg_data[:5]
        
        embed = discord.Embed(title="📊 Ranking Serwerowy", color=discord.Color.pink())
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        curr_user_id = str(interaction.user.id)

        # Sekcja Voice
        voice_text = ""
        for idx, (uid, duration) in enumerate(top_voice, 1):
            user = interaction.guild.get_member(int(uid))
            name = user.display_name if user else f"User {uid}"
            total_seconds = int(duration)
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            
            if days > 0:
                time_str = f"{days}d {hours}h"
            else:
                time_str = f"{hours}h {minutes}m"
            
            medal = ""
            if idx == 1: medal = "🥇 "
            elif idx == 2: medal = "🥈 "
            elif idx == 3: medal = "🥉 "
            else: medal = f"{idx}. "
            
            voice_text += f"{medal}**{name}**: {time_str}\n"
            
        if not voice_text:
            voice_text = "Brak danych."
        else:
            in_top = any(uid == curr_user_id for uid, _ in top_voice)
            if not in_top:
                for idx, (uid, duration) in enumerate(voice_data, 1):
                    if uid == curr_user_id:
                        time_str = format_duration(duration)
                        voice_text += f"\n**Ty**: {idx}. **{interaction.user.display_name}**: {time_str}"
                        break
            
        embed.add_field(name="🎙️ Czas na kanale", value=voice_text, inline=True)

        # Sekcja Wiadomości
        msg_text = ""
        for idx, (uid, count) in enumerate(top_msg, 1):
            user = interaction.guild.get_member(int(uid))
            name = user.display_name if user else f"User {uid}"
            
            medal = ""
            if idx == 1: medal = "🥇 "
            elif idx == 2: medal = "🥈 "
            elif idx == 3: medal = "🥉 "
            else: medal = f"{idx}. "
            
            msg_text += f"{medal}**{name}**: {count}\n"
            
        if not msg_text:
            msg_text = "Brak danych."
        else:
            in_top = any(uid == curr_user_id for uid, _ in top_msg)
            if not in_top:
                for idx, (uid, count) in enumerate(msg_data, 1):
                    if uid == curr_user_id:
                        msg_text += f"\n**Ty**: {idx}. **{interaction.user.display_name}**: {count} wiadomości"
                        break

        embed.add_field(name="💬 Wiadomości", value=msg_text, inline=True)
        embed.set_footer(text="Statystyki są zbierane na bieżąco.")
        
        await interaction.response.send_message(embed=embed)
