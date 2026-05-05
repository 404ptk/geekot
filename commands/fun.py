import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import time
import logging
from datetime import timedelta
import io
from PIL import Image, ImageDraw, ImageFont

STATS_FILE = "txt/server_stats.json"
IGNORED_CHANNEL_ID = 710042604720488520
active_voice_sessions = {}

def is_voice_active(state: discord.VoiceState):
    """Checks if the user's voice time should be counted."""
    if state.channel is None:
        return False
    if state.afk:
        return False
    # Check for both self and server mute/deaf
    if state.self_mute or state.self_deaf or state.mute or state.deaf:
        return False
    return True

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

        was_active = is_voice_active(before)
        is_active = is_voice_active(after)

        # Transition: Not active -> Active (Joined or unmuted)
        if not was_active and is_active:
            active_voice_sessions[user_id] = now
        
        # Transition: Active -> Not active (Left, moved to AFK, or muted)
        elif was_active and not is_active:
            if user_id in active_voice_sessions:
                start_time = active_voice_sessions.pop(user_id)
                duration = now - start_time
                update_voice_time(user_id, duration)

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
                if not member.bot and is_voice_active(member.voice):
                    active_voice_sessions[member.id] = time.time()

    # --- Komendy ---
    @tree.command(name="ranking", description="Wyświetla ranking aktywności serwera", guild=guild_obj)
    async def ranking(interaction: discord.Interaction):
        stats = load_stats()

        # Collect users same as in /ranking
        all_user_ids = set(stats.keys())
        for uid in active_voice_sessions.keys():
            all_user_ids.add(str(uid))

        if not all_user_ids:
            await interaction.response.send_message("Brak danych w rankingu.", ephemeral=True)
            return

        # Prepare data
        voice_data = []
        msg_data = []
        for uid_str in all_user_ids:
            user_stat = stats.get(uid_str, {})
            v_time = user_stat.get("voice_time", 0)
            m_count = user_stat.get("messages", 0)

            uid_int = int(uid_str)
            if uid_int in active_voice_sessions:
                current_session_duration = time.time() - active_voice_sessions[uid_int]
                v_time += current_session_duration

            if v_time > 0:
                voice_data.append((uid_str, v_time))
            if m_count > 0:
                msg_data.append((uid_str, m_count))

        voice_data.sort(key=lambda x: x[1], reverse=True)
        msg_data.sort(key=lambda x: x[1], reverse=True)

        # Load background image
        base_dir = os.path.dirname(__file__)
        bg_path = os.path.join(base_dir, "..", "images", "ranking", "discordranking.png")
        bg_path = os.path.normpath(bg_path)
        if not os.path.exists(bg_path):
            await interaction.response.send_message("Brak obrazka tła: images/ranking/discordranking.png", ephemeral=True)
            return

        try:
            img = Image.open(bg_path).convert("RGBA").copy()
        except Exception as e:
            await interaction.response.send_message(f"Błąd przy otwieraniu obrazka: {e}", ephemeral=True)
            return

        draw = ImageDraw.Draw(img)
        font_path = os.path.join(os.path.dirname(__file__), "..", "images", "font", "roboto", "Roboto-Medium.ttf")
        font_path = os.path.normpath(font_path)

        def fit_font_for_width(text, box_w, init_size=32, min_size=10, font_path=font_path):
            size = init_size
            try:
                while size >= min_size:
                    font = ImageFont.truetype(font_path, size)
                    tw = draw.textlength(text, font=font)
                    if tw <= box_w - 6:
                        return font
                    size -= 1
            except Exception:
                return ImageFont.load_default()
            return ImageFont.load_default()

        # Columns (based on provided image-map coords)
        # voice name col, voice time col, text name col, text count col
        name_col = (129, 554)
        voice_time_col = (569, 704)
        text_name_col = (830, 1245)
        text_count_col = (1263, 1425)

        # Rows Y ranges for top5 (y1,y2)
        rows = [(436,487),(498,549),(560,613),(624,676),(687,737)]

        # Draw top5 voice and messages
        for idx in range(5):
            # Voice column
            if idx < len(voice_data):
                uid, duration = voice_data[idx]
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else f"User {uid}"
                time_str = format_duration(duration)

                y_top, y_bot = rows[idx]
                box_h = y_bot - y_top

                # name
                box_w = name_col[1] - name_col[0]
                font_name = fit_font_for_width(name, box_w, init_size=28)
                bbox = draw.textbbox((0,0), name, font=font_name)
                th = bbox[3]-bbox[1]
                y_text = y_top + (box_h - th)//2
                draw.text((name_col[0]+6, y_text), name, fill="white", font=font_name)

                # time
                box_w = voice_time_col[1] - voice_time_col[0]
                font_time = fit_font_for_width(time_str, box_w, init_size=22)
                bbox = draw.textbbox((0,0), time_str, font=font_time)
                tw = bbox[2]-bbox[0]
                th = bbox[3]-bbox[1]
                x_time = voice_time_col[0] + (box_w - tw)//2
                y_time = y_top + (box_h - th)//2
                draw.text((x_time, y_time), time_str, fill="white", font=font_time)

            # Messages column
            if idx < len(msg_data):
                uid, count = msg_data[idx]
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else f"User {uid}"
                count_str = str(count)

                y_top, y_bot = rows[idx]
                box_h = y_bot - y_top

                # name
                box_w = text_name_col[1] - text_name_col[0]
                font_name2 = fit_font_for_width(name, box_w, init_size=28)
                bbox = draw.textbbox((0,0), name, font=font_name2)
                th = bbox[3]-bbox[1]
                y_text = y_top + (box_h - th)//2
                draw.text((text_name_col[0]+6, y_text), name, fill="white", font=font_name2)

                # count
                box_w = text_count_col[1] - text_count_col[0]
                font_cnt = fit_font_for_width(count_str, box_w, init_size=22)
                bbox = draw.textbbox((0,0), count_str, font=font_cnt)
                tw = bbox[2]-bbox[0]
                th = bbox[3]-bbox[1]
                x_cnt = text_count_col[0] + (box_w - tw)//2
                y_cnt = y_top + (box_h - th)//2
                draw.text((x_cnt, y_cnt), count_str, fill="white", font=font_cnt)

        # If user not in top5, show their position in bottom area
        curr_user_id = str(interaction.user.id)
        # Voice bottom boxes
        bottom_name_col = (344, 605)
        bottom_time_col = (615, 702)
        bottom_text_name_col = (867, 1151)
        bottom_text_count_col = (1165, 1263)
        bottom_y_top = 894
        bottom_y_bot = 943
        box_h = bottom_y_bot - bottom_y_top

        # voice position
        if not any(uid == curr_user_id for uid, _ in voice_data):
            for idx, (uid, duration) in enumerate(voice_data, 1):
                if uid == curr_user_id:
                    name = interaction.user.display_name
                    time_str = format_duration(duration)

                    # name
                    box_w = bottom_name_col[1] - bottom_name_col[0]
                    font_nameb = fit_font_for_width(name, box_w, init_size=24)
                    bbox = draw.textbbox((0,0), name, font=font_nameb)
                    th = bbox[3]-bbox[1]
                    y_text = bottom_y_top + (box_h - th)//2
                    draw.text((bottom_name_col[0]+6, y_text), name, fill="white", font=font_nameb)

                    # time
                    box_w = bottom_time_col[1] - bottom_time_col[0]
                    font_timeb = fit_font_for_width(time_str, box_w, init_size=20)
                    bbox = draw.textbbox((0,0), time_str, font=font_timeb)
                    tw = bbox[2]-bbox[0]
                    x_time = bottom_time_col[0] + (box_w - tw)//2
                    y_time = bottom_y_top + (box_h - (bbox[3]-bbox[1]))//2
                    draw.text((x_time, y_time), time_str, fill="white", font=font_timeb)
                    break

        # messages position
        if not any(uid == curr_user_id for uid, _ in msg_data):
            for idx, (uid, count) in enumerate(msg_data, 1):
                if uid == curr_user_id:
                    name = interaction.user.display_name
                    count_str = str(count)

                    box_w = bottom_text_name_col[1] - bottom_text_name_col[0]
                    font_nameb = fit_font_for_width(name, box_w, init_size=24)
                    bbox = draw.textbbox((0,0), name, font=font_nameb)
                    th = bbox[3]-bbox[1]
                    y_text = bottom_y_top + (box_h - th)//2
                    draw.text((bottom_text_name_col[0]+6, y_text), name, fill="white", font=font_nameb)

                    box_w = bottom_text_count_col[1] - bottom_text_count_col[0]
                    font_cntb = fit_font_for_width(count_str, box_w, init_size=20)
                    bbox = draw.textbbox((0,0), count_str, font=font_cntb)
                    tw = bbox[2]-bbox[0]
                    x_cnt = bottom_text_count_col[0] + (box_w - tw)//2
                    y_cnt = bottom_y_top + (box_h - (bbox[3]-bbox[1]))//2
                    draw.text((x_cnt, y_cnt), count_str, fill="white", font=font_cntb)
                    break

        # Save to buffer and send
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        file = discord.File(fp=buffer, filename="discord_ranking.png")
        await interaction.response.send_message(file=file)
    
    @tree.command(name="avatar", description="Wyświetla avatar użytkownika", guild=guild_obj)
    @app_commands.describe(user="Użytkownik, którego avatar chcesz zobaczyć (opcjonalnie)")
    async def avatar(interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        embed = discord.Embed(title=f"Avatar {target.display_name}", color=discord.Color.pink())
        if target.avatar:
            embed.set_image(url=target.avatar.url)
        else:
            embed.description = "Ten użytkownik nie ma avatara."
        await interaction.response.send_message(embed=embed)

