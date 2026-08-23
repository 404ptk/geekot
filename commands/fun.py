import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import time
import logging
from datetime import timedelta
from typing import List, Optional, Tuple
import io
from PIL import Image, ImageDraw, ImageFont

STATS_FILE = "txt/server_stats.json"
IGNORED_CHANNEL_ID = 710042604720488520
active_voice_sessions = {}
RANKING_TOP_N = 5

# Discord embed background (#2b2d31) — spójnie z /aktywnosc
COLOR_BG = (43, 45, 49, 255)
COLOR_PANEL = (49, 51, 56, 255)
COLOR_ROW = (58, 61, 68, 255)
COLOR_ROW_ALT = (52, 55, 60, 255)
COLOR_HEADER = (72, 76, 84, 255)
COLOR_LABEL = (168, 174, 182, 255)
COLOR_TEXT = (230, 232, 235, 255)
COLOR_MUTED = (130, 136, 144, 255)
COLOR_ACCENT_VOICE = (88, 166, 255, 255)
COLOR_ACCENT_MSG = (163, 113, 247, 255)
COLOR_GOLD = (255, 200, 87, 255)
COLOR_SILVER = (192, 202, 216, 255)
COLOR_BRONZE = (205, 127, 50, 255)
COLOR_SELF = (57, 211, 83, 255)

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


def active_humans_in_channel(channel) -> int:
    if channel is None:
        return 0
    return sum(1 for member in channel.members if not member.bot)


def is_voice_countable(state: discord.VoiceState) -> bool:
    """Voice time counts only when unmuted and not alone on the channel."""
    if not is_voice_active(state):
        return False
    return active_humans_in_channel(state.channel) >= 2


def iter_affected_voice_members(before: discord.VoiceState, after: discord.VoiceState):
    seen_channels = set()
    for channel in (before.channel, after.channel):
        if channel is None or channel.id in seen_channels:
            continue
        seen_channels.add(channel.id)
        for member in channel.members:
            if not member.bot:
                yield member


def apply_voice_session(member: discord.Member, now: float) -> None:
    user_id = member.id
    should_count = is_voice_countable(member.voice)

    if should_count:
        if user_id not in active_voice_sessions:
            active_voice_sessions[user_id] = now
        return

    if user_id in active_voice_sessions:
        start_time = active_voice_sessions.pop(user_id)
        update_voice_time(user_id, now - start_time)

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


def wiadomosci_label(count: int) -> str:
    return "wiadomość" if count == 1 else "wiadomości"


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "images", "font", "roboto", "Roboto-Medium.ttf")),
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "images", "font", "roboto", "Roboto-Regular.ttf")),
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _truncate_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if not text:
        return ""
    if draw.textlength(text, font=font) <= max_width:
        return text
    trimmed = text
    while len(trimmed) > 1 and draw.textlength(trimmed + "…", font=font) > max_width:
        trimmed = trimmed[:-1]
    return trimmed + "…"


def _rank_color(place: int) -> tuple:
    if place == 1:
        return COLOR_GOLD
    if place == 2:
        return COLOR_SILVER
    if place == 3:
        return COLOR_BRONZE
    return COLOR_LABEL


def _resolve_display_name(guild: Optional[discord.Guild], uid_str: str) -> str:
    if guild is None:
        return f"User {uid_str[-4:]}"
    member = guild.get_member(int(uid_str))
    return member.display_name if member else f"User {uid_str[-4:]}"


def _find_user_rank(data: List[Tuple[str, float]], user_id: str) -> Optional[Tuple[int, float]]:
    for idx, (uid, value) in enumerate(data, 1):
        if uid == user_id:
            return idx, value
    return None


def build_ranking_image(
    voice_data: List[Tuple[str, float]],
    msg_data: List[Tuple[str, int]],
    guild: Optional[discord.Guild],
    current_user_id: str,
) -> io.BytesIO:
    scale = 2
    pad = 24 * scale
    gap = 16 * scale
    col_gap = 20 * scale
    title_h = 52 * scale
    title_row_h = 34 * scale
    cols_header_h = 28 * scale
    header_h = title_row_h + cols_header_h
    row_h = 46 * scale
    footer_h = 52 * scale
    radius = 10 * scale

    show_voice_footer = _find_user_rank(voice_data, current_user_id)
    show_msg_footer = _find_user_rank(msg_data, current_user_id)
    in_voice_top = any(uid == current_user_id for uid, _ in voice_data[:RANKING_TOP_N])
    in_msg_top = any(uid == current_user_id for uid, _ in msg_data[:RANKING_TOP_N])
    has_voice_footer = show_voice_footer is not None and not in_voice_top
    has_msg_footer = show_msg_footer is not None and not in_msg_top

    col_w = 420 * scale
    width = pad * 2 + col_w * 2 + col_gap
    rows_h = RANKING_TOP_N * row_h
    footer_block = footer_h + 12 * scale if (has_voice_footer or has_msg_footer) else 0
    height = pad + title_h + gap + header_h + rows_h + footer_block + pad

    img = Image.new("RGBA", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(22 * scale)
    font_header = _load_font(13 * scale)
    font_row = _load_font(15 * scale)
    font_value = _load_font(14 * scale)
    font_footer = _load_font(13 * scale)

    title = "Ranking aktywności serwera"
    tw, th = _text_size(draw, title, font_title)
    draw.text(((width - tw) // 2, pad), title, fill=COLOR_TEXT, font=font_title)

    content_y = pad + title_h + gap
    columns = [
        {
            "x": pad,
            "title": "Kanał głosowy",
            "accent": COLOR_ACCENT_VOICE,
            "value_header": "Czas",
            "data": voice_data[:RANKING_TOP_N],
            "format_value": lambda v: format_duration(v),
            "footer": show_voice_footer if has_voice_footer else None,
            "footer_format": lambda rank, val: f"#{rank}  {_truncate_to_width(draw, _resolve_display_name(guild, current_user_id), font_footer, col_w // 2)}  ·  {format_duration(val)}",
        },
        {
            "x": pad + col_w + col_gap,
            "title": "Wiadomości",
            "accent": COLOR_ACCENT_MSG,
            "value_header": "Liczba",
            "data": msg_data[:RANKING_TOP_N],
            "format_value": lambda v: str(int(v)),
            "footer": show_msg_footer if has_msg_footer else None,
            "footer_format": lambda rank, val: f"#{rank}  {_truncate_to_width(draw, _resolve_display_name(guild, current_user_id), font_footer, col_w // 2)}  ·  {int(val)} {wiadomosci_label(int(val))}",
        },
    ]

    for col in columns:
        x = col["x"]
        panel = (x, content_y, x + col_w, content_y + header_h + rows_h)
        try:
            draw.rounded_rectangle(panel, radius=radius, fill=COLOR_PANEL)
        except Exception:
            draw.rectangle(panel, fill=COLOR_PANEL)

        accent_bar = (x, content_y, x + 4 * scale, content_y + header_h + rows_h)
        draw.rectangle(accent_bar, fill=col["accent"])

        draw.text((x + 16 * scale, content_y + 10 * scale), col["title"], fill=col["accent"], font=font_header)

        header_y = content_y + title_row_h + 6 * scale
        draw.text((x + 16 * scale, header_y), "#", fill=COLOR_MUTED, font=font_header)
        draw.text((x + 52 * scale, header_y), "Użytkownik", fill=COLOR_MUTED, font=font_header)
        value_w, _ = _text_size(draw, col["value_header"], font_header)
        draw.text((x + col_w - value_w - 16 * scale, header_y), col["value_header"], fill=COLOR_MUTED, font=font_header)

        draw.line(
            (x + 12 * scale, content_y + header_h - 4 * scale, x + col_w - 12 * scale, content_y + header_h - 4 * scale),
            fill=COLOR_HEADER,
            width=max(1, scale),
        )

        for idx in range(RANKING_TOP_N):
            row_y = content_y + header_h + idx * row_h
            row_fill = COLOR_ROW if idx % 2 == 0 else COLOR_ROW_ALT
            draw.rectangle((x + 8 * scale, row_y, x + col_w - 8 * scale, row_y + row_h), fill=row_fill)

            if idx < len(col["data"]):
                uid, value = col["data"][idx]
                place = idx + 1
                name = _resolve_display_name(guild, uid)
                value_str = col["format_value"](value)

                draw.text((x + 16 * scale, row_y + 14 * scale), str(place), fill=_rank_color(place), font=font_row)

                name_max_w = col_w - 52 * scale - 100 * scale
                name_draw = _truncate_to_width(draw, name, font_row, name_max_w)
                draw.text((x + 52 * scale, row_y + 14 * scale), name_draw, fill=COLOR_TEXT, font=font_row)

                vw, _ = _text_size(draw, value_str, font_value)
                draw.text((x + col_w - vw - 16 * scale, row_y + 15 * scale), value_str, fill=COLOR_LABEL, font=font_value)
            else:
                draw.text((x + 52 * scale, row_y + 14 * scale), "—", fill=COLOR_MUTED, font=font_row)

        if col["footer"]:
            rank, val = col["footer"]
            footer_y = content_y + header_h + rows_h + 8 * scale
            footer_box = (x, footer_y, x + col_w, footer_y + footer_h)
            try:
                draw.rounded_rectangle(footer_box, radius=8 * scale, fill=(38, 40, 44, 255))
            except Exception:
                draw.rectangle(footer_box, fill=(38, 40, 44, 255))

            footer_text = col["footer_format"](rank, val)
            fw, fh = _text_size(draw, footer_text, font_footer)
            draw.text((x + (col_w - fw) // 2, footer_y + (footer_h - fh) // 2), footer_text, fill=COLOR_SELF, font=font_footer)

    if scale > 1:
        img = img.resize((width // scale, height // scale), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

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
        now = time.time()
        for affected in iter_affected_voice_members(before, after):
            apply_voice_session(affected, now)

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
        now = time.time()
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot:
                    apply_voice_session(member, now)

    # --- Komendy ---
    @tree.command(name="ranking", description="Wyświetla ranking aktywności serwera", guild=guild_obj)
    async def ranking(interaction: discord.Interaction):
        stats = load_stats()

        all_user_ids = set(stats.keys())
        for uid in active_voice_sessions.keys():
            all_user_ids.add(str(uid))

        if not all_user_ids:
            await interaction.response.send_message("Brak danych w rankingu.", ephemeral=True)
            return

        voice_data = []
        msg_data = []
        for uid_str in all_user_ids:
            user_stat = stats.get(uid_str, {})
            v_time = user_stat.get("voice_time", 0)
            m_count = user_stat.get("messages", 0)

            uid_int = int(uid_str)
            if uid_int in active_voice_sessions:
                v_time += time.time() - active_voice_sessions[uid_int]

            if v_time > 0:
                voice_data.append((uid_str, v_time))
            if m_count > 0:
                msg_data.append((uid_str, m_count))

        voice_data.sort(key=lambda x: x[1], reverse=True)
        msg_data.sort(key=lambda x: x[1], reverse=True)

        if not voice_data and not msg_data:
            await interaction.response.send_message("Brak danych w rankingu.", ephemeral=True)
            return

        try:
            buffer = build_ranking_image(
                voice_data,
                msg_data,
                interaction.guild,
                str(interaction.user.id),
            )
            file = discord.File(fp=buffer, filename="ranking.png")
            await interaction.response.send_message(file=file)
        except Exception as exc:
            logging.error(f"Failed to generate ranking image: {exc}")
            await interaction.response.send_message(
                f"Nie udało się wygenerować rankingu: {exc}",
                ephemeral=True,
            )
    
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

