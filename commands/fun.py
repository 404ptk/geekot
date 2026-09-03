import asyncio
import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import time
import logging
import threading
from datetime import timedelta
from typing import List, Optional, Tuple
import io
from PIL import Image, ImageDraw, ImageFont

STATS_FILE = "txt/server_stats.json"
IGNORED_CHANNEL_ID = 710042604720488520
VOICE_EXEMPT_USER_ID = 391289282125365248
VOICE_EXEMPT_PAIR_USER_ID = 1309165290868965507
active_voice_sessions = {}
RANKING_TOP_N = 5
_stats_lock = threading.Lock()
CLIENT_REF: Optional[discord.Client] = None
GUILD_ID: Optional[int] = None

# Discord embed background (#2b2d31) — spójnie z /aktywnosc
COLOR_BG = (43, 45, 49, 255)
COLOR_PANEL = (49, 51, 56, 255)
COLOR_ROW = (56, 59, 66, 255)
COLOR_ROW_SELF = (46, 62, 52, 255)
COLOR_BAR_TRACK = (58, 61, 68, 255)
COLOR_LABEL = (168, 174, 182, 255)
COLOR_TEXT = (230, 232, 235, 255)
COLOR_MUTED = (130, 136, 144, 255)
COLOR_ACCENT_VOICE = (88, 166, 255, 255)
COLOR_ACCENT_VOICE_DIM = (56, 104, 160, 255)
COLOR_ACCENT_MSG = (163, 113, 247, 255)
COLOR_ACCENT_MSG_DIM = (102, 72, 156, 255)
COLOR_GOLD = (255, 200, 87, 255)
COLOR_GOLD_DIM = (120, 92, 36, 255)
COLOR_SILVER = (192, 202, 216, 255)
COLOR_SILVER_DIM = (78, 84, 94, 255)
COLOR_BRONZE = (205, 127, 50, 255)
COLOR_BRONZE_DIM = (102, 64, 28, 255)
COLOR_SELF = (57, 211, 83, 255)

def is_voice_active(state: Optional[discord.VoiceState]) -> bool:
    """Checks if the user's voice time should be counted."""
    if state is None or state.channel is None:
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


def is_exempt_voice_pair(channel, user_id: int) -> bool:
    """Czas obu użytkowników nie liczy się, gdy na kanale są tylko VOICE_EXEMPT_USER_ID i VOICE_EXEMPT_PAIR_USER_ID."""
    if channel is None or user_id not in (VOICE_EXEMPT_USER_ID, VOICE_EXEMPT_PAIR_USER_ID):
        return False
    human_ids = {member.id for member in channel.members if not member.bot}
    return human_ids == {VOICE_EXEMPT_USER_ID, VOICE_EXEMPT_PAIR_USER_ID}


def is_voice_countable(state: Optional[discord.VoiceState], user_id: Optional[int] = None) -> bool:
    """Voice time counts only when unmuted and not alone on the channel."""
    if not is_voice_active(state):
        return False
    if active_humans_in_channel(state.channel) < 2:
        return False
    if user_id is not None and is_exempt_voice_pair(state.channel, user_id):
        return False
    return True


def iter_affected_voice_members(before: discord.VoiceState, after: discord.VoiceState):
    seen_channels = set()
    for channel in (before.channel, after.channel):
        if channel is None or channel.id in seen_channels:
            continue
        seen_channels.add(channel.id)
        for member in channel.members:
            if not member.bot:
                yield member


def get_member_in_voice(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
    channels = list(guild.voice_channels) + list(getattr(guild, "stage_channels", []))
    for channel in channels:
        for member in channel.members:
            if member.id == user_id and not member.bot:
                return member
    return None


def is_user_in_guild_voice(guild: discord.Guild, user_id: int) -> bool:
    return get_member_in_voice(guild, user_id) is not None


def reconcile_voice_sessions(guild: Optional[discord.Guild], now: float, stats: Optional[dict] = None) -> bool:
    """Flush stale sessions for users who are no longer in countable voice."""
    changed = False

    for user_id in list(active_voice_sessions.keys()):
        if guild is None:
            if flush_voice_session(user_id, now, stats) > 0:
                changed = True
            continue

        member = get_member_in_voice(guild, user_id)
        if member is None or not is_voice_countable(member.voice, user_id):
            if flush_voice_session(user_id, now, stats) > 0:
                changed = True

    return changed


def credit_voice_time(stats: dict, user_id: int, duration: float) -> dict:
    if duration <= 1:
        return stats

    user_id_str = str(user_id)
    if user_id_str not in stats:
        stats[user_id_str] = {"messages": 0, "voice_time": 0}

    stats[user_id_str]["voice_time"] = stats[user_id_str].get("voice_time", 0) + duration
    return stats


def flush_voice_session(user_id: int, now: float, stats: Optional[dict] = None) -> float:
    start_time = active_voice_sessions.pop(user_id, None)
    if start_time is None:
        return 0.0

    duration = now - start_time
    if stats is None:
        with _stats_lock:
            loaded = load_stats()
            loaded = credit_voice_time(loaded, user_id, duration)
            save_stats(loaded)
        return max(duration, 0.0) if duration > 1 else 0.0

    credit_voice_time(stats, user_id, duration)
    return max(duration, 0.0) if duration > 1 else 0.0


def apply_voice_session(member: discord.Member, now: float) -> None:
    user_id = member.id
    should_count = is_voice_countable(member.voice, member.id)

    if should_count:
        if user_id not in active_voice_sessions:
            active_voice_sessions[user_id] = now
        return

    flush_voice_session(user_id, now)

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
    with _stats_lock:
        stats = load_stats()
        stats = credit_voice_time(stats, user_id, duration)
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


def _load_font(size: int, *, weight: str = "regular") -> ImageFont.ImageFont:
    """weight: regular | medium | semibold | bold"""
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "images", "font"))
    weight = weight.lower()
    inter_map = {
        "bold": "Inter-Bold.ttf",
        "semibold": "Inter-SemiBold.ttf",
        "medium": "Inter-Medium.ttf",
        "regular": "Inter-Regular.ttf",
    }
    roboto_map = {
        "bold": "Roboto-Bold.ttf",
        "semibold": "Roboto-Medium.ttf",
        "medium": "Roboto-Medium.ttf",
        "regular": "Roboto-Regular.ttf",
    }
    preferred = [
        os.path.join(base, "inter", inter_map.get(weight, "Inter-Regular.ttf")),
        os.path.join(base, "inter", "Inter-SemiBold.ttf"),
        os.path.join(base, "inter", "Inter-Medium.ttf"),
        os.path.join(base, "inter", "Inter-Regular.ttf"),
        os.path.join(base, "roboto", roboto_map.get(weight, "Roboto-Regular.ttf")),
        os.path.join(base, "roboto", "Roboto-Medium.ttf"),
        os.path.join(base, "roboto", "Roboto-Regular.ttf"),
        r"C:\Windows\Fonts\segoeuib.ttf" if weight in ("bold", "semibold") else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if weight in ("bold", "semibold") else r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if weight in ("bold", "semibold") else r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight in ("bold", "semibold") else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in preferred:
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


def _rank_badge_colors(place: int) -> Tuple[tuple, tuple]:
    if place == 1:
        return COLOR_GOLD, COLOR_GOLD_DIM
    if place == 2:
        return COLOR_SILVER, COLOR_SILVER_DIM
    if place == 3:
        return COLOR_BRONZE, COLOR_BRONZE_DIM
    return COLOR_LABEL, COLOR_BAR_TRACK


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


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, box, radius: int, fill=None, outline=None, width: int = 1):
    try:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    except Exception:
        draw.rectangle(box, fill=fill, outline=outline, width=width)


def _draw_rank_badge(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    place: int,
    font: ImageFont.ImageFont,
    scale: int,
) -> None:
    r = 15 * scale
    fg, bg = _rank_badge_colors(place)
    box = (cx - r, cy - r, cx + r, cy + r)
    if place <= 3:
        draw.ellipse(box, fill=bg, outline=fg, width=max(2, scale))
        label_color = fg
    else:
        draw.ellipse(box, fill=bg)
        label_color = COLOR_MUTED

    label = str(place)
    # wyśrodkuj po realnym atramentu glifu, nie po bounding boxie fontu
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    x = cx - (left + right) // 2
    y = cy - (top + bottom) // 2
    draw.text((x, y), label, fill=label_color, font=font)


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    ratio: float,
    fill: tuple,
    scale: int,
) -> None:
    ratio = max(0.0, min(1.0, ratio))
    _draw_rounded_rect(draw, (x, y, x + width, y + height), radius=height // 2, fill=COLOR_BAR_TRACK)
    fill_w = max(height if ratio > 0 else 0, int(width * ratio))
    if fill_w > 0:
        _draw_rounded_rect(draw, (x, y, x + fill_w, y + height), radius=height // 2, fill=fill)


def build_ranking_image(
    voice_data: List[Tuple[str, float]],
    msg_data: List[Tuple[str, int]],
    guild: Optional[discord.Guild],
    current_user_id: str,
) -> io.BytesIO:
    scale = 2
    pad = 28 * scale
    gap = 16 * scale
    col_gap = 18 * scale
    title_h = 64 * scale
    header_h = 42 * scale
    row_h = 48 * scale
    row_gap = 8 * scale
    footer_h = 44 * scale
    radius = 14 * scale

    show_voice_footer = _find_user_rank(voice_data, current_user_id)
    show_msg_footer = _find_user_rank(msg_data, current_user_id)
    in_voice_top = any(uid == current_user_id for uid, _ in voice_data[:RANKING_TOP_N])
    in_msg_top = any(uid == current_user_id for uid, _ in msg_data[:RANKING_TOP_N])
    has_voice_footer = show_voice_footer is not None and not in_voice_top
    has_msg_footer = show_msg_footer is not None and not in_msg_top

    col_w = 430 * scale
    width = pad * 2 + col_w * 2 + col_gap
    rows_h = RANKING_TOP_N * row_h + (RANKING_TOP_N - 1) * row_gap
    footer_gap = 12 * scale
    footer_block = footer_h + footer_gap if (has_voice_footer or has_msg_footer) else 0
    height = pad + title_h + gap + header_h + rows_h + 16 * scale + footer_block + pad

    img = Image.new("RGBA", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(30 * scale, weight="bold")
    font_sub = _load_font(12 * scale, weight="medium")
    font_header = _load_font(14 * scale, weight="semibold")
    font_badge = _load_font(13 * scale, weight="bold")
    font_row = _load_font(15 * scale, weight="semibold")
    font_value = _load_font(14 * scale, weight="semibold")
    font_footer = _load_font(13 * scale, weight="semibold")

    title = "Ranking aktywności"
    draw.text((width // 2, pad + 4 * scale), title, fill=COLOR_TEXT, font=font_title, anchor="ma")
    subtitle = "top 5 · voice i wiadomości"
    draw.text((width // 2, pad + 40 * scale), subtitle, fill=COLOR_MUTED, font=font_sub, anchor="ma")

    content_y = pad + title_h + gap
    columns = [
        {
            "x": pad,
            "title": "Kanał głosowy",
            "accent": COLOR_ACCENT_VOICE,
            "bar": COLOR_ACCENT_VOICE,
            "bar_dim": COLOR_ACCENT_VOICE_DIM,
            "data": voice_data[:RANKING_TOP_N],
            "format_value": lambda v: format_duration(v),
            "footer": show_voice_footer if has_voice_footer else None,
        },
        {
            "x": pad + col_w + col_gap,
            "title": "Wiadomości",
            "accent": COLOR_ACCENT_MSG,
            "bar": COLOR_ACCENT_MSG,
            "bar_dim": COLOR_ACCENT_MSG_DIM,
            "data": msg_data[:RANKING_TOP_N],
            "format_value": lambda v: f"{int(v):,}".replace(",", " "),
            "footer": show_msg_footer if has_msg_footer else None,
        },
    ]

    for col in columns:
        x = col["x"]
        panel_bottom = content_y + header_h + rows_h + 16 * scale
        _draw_rounded_rect(draw, (x, content_y, x + col_w, panel_bottom), radius=radius, fill=COLOR_PANEL)

        # accent pill + title
        pill_y = content_y + 14 * scale
        _draw_rounded_rect(
            draw,
            (x + 16 * scale, pill_y + 4 * scale, x + 28 * scale, pill_y + 16 * scale),
            radius=6 * scale,
            fill=col["accent"],
        )
        draw.text((x + 36 * scale, pill_y), col["title"], fill=COLOR_TEXT, font=font_header)

        leader = col["data"][0][1] if col["data"] else 0
        rows_top = content_y + header_h

        for idx in range(RANKING_TOP_N):
            row_y = rows_top + idx * (row_h + row_gap)
            row_box = (x + 12 * scale, row_y, x + col_w - 12 * scale, row_y + row_h)

            if idx >= len(col["data"]):
                _draw_rounded_rect(draw, row_box, radius=10 * scale, fill=COLOR_BAR_TRACK)
                draw.text((x + 58 * scale, row_y + row_h // 2), "—", fill=COLOR_MUTED, font=font_row, anchor="lm")
                continue

            uid, value = col["data"][idx]
            place = idx + 1
            is_self = uid == current_user_id
            name = _resolve_display_name(guild, uid)
            value_str = col["format_value"](value)
            ratio = (float(value) / float(leader)) if leader else 0.0

            row_fill = COLOR_ROW_SELF if is_self else COLOR_ROW
            _draw_rounded_rect(draw, row_box, radius=10 * scale, fill=row_fill)
            if is_self:
                _draw_rounded_rect(
                    draw,
                    row_box,
                    radius=10 * scale,
                    outline=COLOR_SELF,
                    width=max(1, scale),
                )

            badge_cx = x + 34 * scale
            badge_cy = row_y + row_h // 2
            _draw_rank_badge(draw, badge_cx, badge_cy, place, font_badge, scale)

            name_x = x + 56 * scale
            value_w, _ = _text_size(draw, value_str, font_value)
            name_max_w = col_w - 56 * scale - value_w - 40 * scale
            name_draw = _truncate_to_width(draw, name, font_row, name_max_w)
            name_color = COLOR_SELF if is_self else COLOR_TEXT

            text_y = row_y + 8 * scale
            draw.text((name_x, text_y), name_draw, fill=name_color, font=font_row)
            draw.text(
                (x + col_w - 24 * scale, text_y),
                value_str,
                fill=COLOR_LABEL,
                font=font_value,
                anchor="ra",
            )

            bar_x = name_x
            bar_y = text_y + 23 * scale
            bar_w = col_w - 56 * scale - 36 * scale
            bar_fill = col["bar"] if place == 1 else col["bar_dim"]
            if is_self and place > 1:
                bar_fill = COLOR_SELF
            _draw_progress_bar(draw, bar_x, bar_y, bar_w, 6 * scale, ratio, bar_fill, scale)

        if col["footer"]:
            rank, val = col["footer"]
            footer_y = panel_bottom + footer_gap
            footer_box = (x, footer_y, x + col_w, footer_y + footer_h)
            _draw_rounded_rect(draw, footer_box, radius=10 * scale, fill=COLOR_ROW_SELF)
            _draw_rounded_rect(
                draw,
                footer_box,
                radius=10 * scale,
                outline=COLOR_SELF,
                width=max(1, scale),
            )

            badge_cx = x + 28 * scale
            badge_cy = footer_y + footer_h // 2
            # mini badge z miejscem (bez złota/srebra — to pozycja poza topką)
            br = 13 * scale
            draw.ellipse(
                (badge_cx - br, badge_cy - br, badge_cx + br, badge_cy + br),
                fill=COLOR_BAR_TRACK,
                outline=COLOR_SELF,
                width=max(1, scale),
            )
            rank_label = str(rank)
            left, top, right, bottom = draw.textbbox((0, 0), rank_label, font=font_badge)
            draw.text(
                (badge_cx - (left + right) // 2, badge_cy - (top + bottom) // 2),
                rank_label,
                fill=COLOR_SELF,
                font=font_badge,
            )

            name = _truncate_to_width(
                draw,
                _resolve_display_name(guild, current_user_id),
                font_footer,
                col_w // 2,
            )
            value_str = col["format_value"](val)
            draw.text((x + 50 * scale, badge_cy), name, fill=COLOR_SELF, font=font_footer, anchor="lm")
            draw.text(
                (x + col_w - 18 * scale, badge_cy),
                value_str,
                fill=COLOR_SELF,
                font=font_footer,
                anchor="rm",
            )

    if scale > 1:
        img = img.resize((width // scale, height // scale), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

@tasks.loop(minutes=2)
async def commit_voice_stats():
    if not active_voice_sessions:
        return

    now = time.time()
    guild = CLIENT_REF.get_guild(GUILD_ID) if CLIENT_REF and GUILD_ID else None

    with _stats_lock:
        stats = load_stats()
        changed = reconcile_voice_sessions(guild, now, stats)

        for user_id, start_time in list(active_voice_sessions.items()):
            member = get_member_in_voice(guild, user_id) if guild else None
            if member is None or not is_voice_countable(member.voice, user_id):
                if flush_voice_session(user_id, now, stats) > 0:
                    changed = True
                continue

            duration = now - start_time
            if duration > 1:
                credit_voice_time(stats, user_id, duration)
                active_voice_sessions[user_id] = now
                changed = True

        if changed:
            save_stats(stats)

async def setup_fun_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int):
    global CLIENT_REF, GUILD_ID
    CLIENT_REF = client
    GUILD_ID = guild_id
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
        if member.bot or member.guild is None or member.guild.id != guild_id:
            return

        now = time.time()
        apply_voice_session(member, now)

        seen_ids = {member.id}
        for affected in iter_affected_voice_members(before, after):
            if affected.id in seen_ids:
                continue
            seen_ids.add(affected.id)
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
        voice_channels = list(guild.voice_channels) + list(getattr(guild, "stage_channels", []))
        for vc in voice_channels:
            for member in vc.members:
                if not member.bot:
                    apply_voice_session(member, now)

    # --- Komendy ---
    @tree.command(name="ranking", description="Wyświetla ranking aktywności serwera", guild=guild_obj)
    async def ranking(interaction: discord.Interaction):
        await interaction.response.defer()

        now = time.time()
        guild = interaction.guild or client.get_guild(guild_id)

        with _stats_lock:
            stats = load_stats()
            if reconcile_voice_sessions(guild, now, stats):
                save_stats(stats)

        stats = load_stats()

        all_user_ids = set(stats.keys())
        for uid in active_voice_sessions.keys():
            all_user_ids.add(str(uid))

        if not all_user_ids:
            await interaction.followup.send("Brak danych w rankingu.", ephemeral=True)
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
            await interaction.followup.send("Brak danych w rankingu.", ephemeral=True)
            return

        try:
            buffer = await asyncio.to_thread(
                build_ranking_image,
                voice_data,
                msg_data,
                interaction.guild,
                str(interaction.user.id),
            )
            file = discord.File(fp=buffer, filename="ranking.png")
            await interaction.followup.send(file=file)
        except discord.NotFound:
            logging.warning("Ranking interaction expired before the reply could be sent.")
        except Exception as exc:
            logging.error(f"Failed to generate ranking image: {exc}")
            try:
                await interaction.followup.send(
                    f"Nie udało się wygenerować rankingu: {exc}",
                    ephemeral=True,
                )
            except discord.NotFound:
                logging.warning("Ranking interaction expired before the reply could be sent.")
    
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

