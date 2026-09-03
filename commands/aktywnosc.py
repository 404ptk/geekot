import asyncio
import io
import json
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone, time as dt_time
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont

from commands.fun import get_member_in_voice, is_voice_countable, iter_affected_voice_members

DATA_FILE = "txt/aktywnosc.json"
WINDOW_DAYS = 30
KEEP_DAYS = 45
COMMIT_INTERVAL_MINUTES = 1

try:
    TZ = ZoneInfo("Europe/Warsaw")
except Exception:
    TZ = datetime.now().astimezone().tzinfo or timezone(timedelta(hours=2))

# GitHub-style squares on Discord embed background (#2b2d31)
COLOR_BG = (43, 45, 49, 255)
COLOR_EMPTY = (58, 61, 68, 255)
COLOR_OUT_OF_RANGE = (48, 50, 54, 255)
COLOR_LABEL = (168, 174, 182, 255)
COLOR_TODAY_BORDER = (201, 209, 217, 255)

# Progi i zieleń jak na GitHubie: im dłużej na VC, tym jaśniej
LEVEL_THRESHOLDS = (
    5 * 60,        # ≥ 5 min
    30 * 60,       # ≥ 30 min
    60 * 60,       # ≥ 1 h
    3 * 60 * 60,   # ≥ 3 h
    5 * 60 * 60,   # ≥ 5 h
)
LEVEL_COLORS = (
    COLOR_EMPTY,              # 0: brak / < 5 min
    (14, 68, 41, 255),        # 1: ≥ 5 min   #0e4429
    (0, 109, 50, 255),        # 2: ≥ 30 min  #006d32
    (38, 166, 65, 255),       # 3: ≥ 1 h     #26a641
    (57, 211, 83, 255),       # 4: ≥ 3 h     #39d353
    (94, 240, 127, 255),      # 5: ≥ 5 h     jaśniejszy lime
)
LEVEL_LABELS = ("—", "5m", "30m", "1h", "3h", "5h")

ETAT_THRESHOLD = 8 * 60 * 60  # ≥ 8 h
COLOR_ETAT = (240, 193, 75, 255)

WEEKDAY_LABELS = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]
MONTHS_SHORT = ["", "Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"]
MONTHS_GENITIVE = {
    1: "stycznia",
    2: "lutego",
    3: "marca",
    4: "kwietnia",
    5: "maja",
    6: "czerwca",
    7: "lipca",
    8: "sierpnia",
    9: "września",
    10: "października",
    11: "listopada",
    12: "grudnia",
}

_file_lock = threading.Lock()
active_voice_sessions: Dict[int, float] = {}
CLIENT_REF: Optional[discord.Client] = None
GUILD_ID: Optional[int] = None


def now_warsaw() -> datetime:
    return datetime.now(TZ)


def today_warsaw() -> date:
    return now_warsaw().date()


def load_activity() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_activity(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE) or ".", exist_ok=True)
    cutoff = (today_warsaw() - timedelta(days=KEEP_DAYS)).isoformat()
    pruned = {}
    for uid, days in data.items():
        if not isinstance(days, dict):
            continue
        kept = {day: seconds for day, seconds in days.items() if isinstance(day, str) and day >= cutoff}
        if kept:
            pruned[uid] = kept
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(pruned, f, indent=4)


def add_seconds(data: dict, user_id: int, day: date, seconds: float) -> None:
    if seconds <= 0:
        return
    uid = str(user_id)
    user_days = data.setdefault(uid, {})
    key = day.isoformat()
    user_days[key] = user_days.get(key, 0) + seconds


def iter_session_chunks(start_ts: float, end_ts: float) -> List[Tuple[date, float]]:
    if end_ts <= start_ts:
        return []

    start_dt = datetime.fromtimestamp(start_ts, TZ)
    end_dt = datetime.fromtimestamp(end_ts, TZ)
    chunks: List[Tuple[date, float]] = []
    cursor = start_dt

    while cursor.date() < end_dt.date():
        next_midnight = datetime.combine(cursor.date() + timedelta(days=1), dt_time.min, tzinfo=TZ)
        chunks.append((cursor.date(), (next_midnight - cursor).total_seconds()))
        cursor = next_midnight

    remaining = (end_dt - cursor).total_seconds()
    if remaining > 0:
        chunks.append((end_dt.date(), remaining))
    return chunks


def credit_session(user_id: int, start_ts: float, end_ts: float) -> None:
    chunks = iter_session_chunks(start_ts, end_ts)
    if not chunks:
        return
    with _file_lock:
        data = load_activity()
        for day, seconds in chunks:
            add_seconds(data, user_id, day, seconds)
        save_activity(data)


def flush_daily_voice_session(user_id: int, now: float, data: Optional[dict] = None) -> float:
    start_ts = active_voice_sessions.pop(user_id, None)
    if start_ts is None:
        return 0.0

    duration = now - start_ts
    if duration <= 1:
        return 0.0

    if data is None:
        credit_session(user_id, start_ts, now)
    else:
        for day, seconds in iter_session_chunks(start_ts, now):
            add_seconds(data, user_id, day, seconds)

    return duration


def reconcile_daily_voice_sessions(guild: Optional[discord.Guild], now: float, data: Optional[dict] = None) -> bool:
    changed = False

    for user_id in list(active_voice_sessions.keys()):
        if guild is None:
            if flush_daily_voice_session(user_id, now, data) > 0:
                changed = True
            continue

        member = get_member_in_voice(guild, user_id)
        if member is None or not is_voice_countable(member.voice, user_id):
            if flush_daily_voice_session(user_id, now, data) > 0:
                changed = True

    return changed


def seconds_by_day_for_user(user_id: int) -> Dict[str, float]:
    with _file_lock:
        data = load_activity()
        raw = data.get(str(user_id), {})
        seconds_map = {day: float(value) for day, value in raw.items() if isinstance(value, (int, float))}

    start_ts = active_voice_sessions.get(user_id)
    if start_ts is not None:
        for day, seconds in iter_session_chunks(start_ts, time.time()):
            key = day.isoformat()
            seconds_map[key] = seconds_map.get(key, 0) + seconds
    return seconds_map


def window_dates(today: Optional[date] = None) -> List[date]:
    today = today or today_warsaw()
    start = today - timedelta(days=WINDOW_DAYS - 1)
    return [start + timedelta(days=i) for i in range(WINDOW_DAYS)]


def activity_level(seconds: float) -> int:
    level = 0
    for threshold in LEVEL_THRESHOLDS:
        if seconds >= threshold:
            level += 1
        else:
            break
    return level


def color_for_seconds(seconds: float) -> tuple:
    if seconds >= ETAT_THRESHOLD:
        return COLOR_ETAT
    return LEVEL_COLORS[activity_level(seconds)]


def is_day_active(seconds: float) -> bool:
    return activity_level(seconds) > 0


def dni_label(count: int) -> str:
    if count == 1:
        return "dzień"
    return "dni"


def format_duration(seconds: float) -> str:
    total = int(max(0, seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    elif secs > 0:
        parts.append(f"{secs}s")
    else:
        parts.append("0m")
    return " ".join(parts)


def format_date_pl(day: date) -> str:
    return f"{day.day} {MONTHS_GENITIVE[day.month]}"


def compute_stats(seconds_map: Dict[str, float], today: Optional[date] = None) -> dict:
    today = today or today_warsaw()
    days = window_dates(today)
    active_flags = [is_day_active(seconds_map.get(day.isoformat(), 0)) for day in days]
    total_seconds = sum(seconds_map.get(day.isoformat(), 0) for day in days)
    active_count = sum(1 for flag in active_flags if flag)

    longest = 0
    current_run = 0
    for flag in active_flags:
        if flag:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 0

    streak_idx = len(active_flags) - 1
    if streak_idx >= 0 and not active_flags[streak_idx] and streak_idx > 0:
        streak_idx -= 1
    current_streak = 0
    while streak_idx >= 0 and active_flags[streak_idx]:
        current_streak += 1
        streak_idx -= 1

    return {
        "days": days,
        "active_flags": active_flags,
        "active_count": active_count,
        "total_seconds": total_seconds,
        "current_streak": current_streak,
        "longest_streak": longest,
        "today": today,
        "seconds_by_day": {day: seconds_map.get(day.isoformat(), 0.0) for day in days},
    }


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


def build_heatmap_image(stats: dict) -> io.BytesIO:
    today = stats["today"]
    days: List[date] = stats["days"]
    start = days[0]
    in_window = {day for day in days}
    seconds_lookup = stats.get("seconds_by_day", {})

    grid_start = start - timedelta(days=start.weekday())
    last_grid_day = today + timedelta(days=(6 - today.weekday()))
    num_weeks = ((last_grid_day - grid_start).days // 7) + 1

    scale = 2
    cell = 52 * scale
    gap = 12 * scale
    radius = 10 * scale
    pad = 28 * scale
    label_w = 48 * scale
    month_h = 32 * scale
    legend_h = 62 * scale
    pitch = cell + gap

    grid_w = num_weeks * pitch - gap
    grid_h = 7 * pitch - gap
    width = pad + label_w + grid_w + pad
    height = pad + month_h + grid_h + pad + legend_h

    img = Image.new("RGBA", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)
    font_small = _load_font(13 * scale)
    font_legend = _load_font(14 * scale)

    origin_x = pad + label_w
    origin_y = pad + month_h

    last_month = None
    for week in range(num_weeks):
        for row in range(7):
            day = grid_start + timedelta(days=week * 7 + row)
            if start <= day <= today and day.month != last_month:
                label = MONTHS_SHORT[day.month]
                x = origin_x + week * pitch
                draw.text((x, pad - 2 * scale), label, fill=COLOR_LABEL, font=font_small)
                last_month = day.month
                break

    for row, label in enumerate(WEEKDAY_LABELS):
        tw, th = _text_size(draw, label, font_small)
        x = pad + label_w - tw - 8 * scale
        y = origin_y + row * pitch + (cell - th) // 2
        draw.text((x, y), label, fill=COLOR_LABEL, font=font_small)

    for week in range(num_weeks):
        for row in range(7):
            day = grid_start + timedelta(days=week * 7 + row)
            x1 = origin_x + week * pitch
            y1 = origin_y + row * pitch
            x2 = x1 + cell
            y2 = y1 + cell
            box = (x1, y1, x2, y2)

            if day in in_window:
                fill = color_for_seconds(seconds_lookup.get(day, 0.0))
            else:
                fill = COLOR_OUT_OF_RANGE

            try:
                draw.rounded_rectangle(box, radius=radius, fill=fill)
            except Exception:
                draw.rectangle(box, fill=fill)

            if day == today:
                try:
                    draw.rounded_rectangle(box, radius=radius, outline=COLOR_TODAY_BORDER, width=max(2, scale))
                except Exception:
                    draw.rectangle(box, outline=COLOR_TODAY_BORDER, width=max(2, scale))

    legend_y = origin_y + grid_h + 16 * scale
    font_legend_small = _load_font(11 * scale)
    less_label = ""
    more_label = ""
    less_w, less_h = _text_size(draw, less_label, font_legend)
    sq = 16 * scale
    legend_pitch = 40 * scale
    squares_w = len(LEVEL_COLORS) * legend_pitch - (legend_pitch - sq)
    legend_x = origin_x
    draw.text((legend_x, legend_y + (sq - less_h) // 2), less_label, fill=COLOR_LABEL, font=font_legend)
    squares_x = legend_x + less_w + 12 * scale

    for i, fill in enumerate(LEVEL_COLORS):
        x1 = squares_x + i * legend_pitch
        box = (x1, legend_y, x1 + sq, legend_y + sq)
        try:
            draw.rounded_rectangle(box, radius=4 * scale, fill=fill)
        except Exception:
            draw.rectangle(box, fill=fill)
        label = LEVEL_LABELS[i]
        tw, _ = _text_size(draw, label, font_legend_small)
        draw.text(
            (x1 + (sq - tw) // 2, legend_y + sq + 4 * scale),
            label,
            fill=COLOR_LABEL,
            font=font_legend_small,
        )

    etat_gap = 16 * scale
    etat_x = squares_x + squares_w + etat_gap
    etat_box = (etat_x, legend_y, etat_x + sq, legend_y + sq)
    try:
        draw.rounded_rectangle(etat_box, radius=4 * scale, fill=COLOR_ETAT)
    except Exception:
        draw.rectangle(etat_box, fill=COLOR_ETAT)
    etat_label = "etat"
    etat_tw, _ = _text_size(draw, etat_label, font_legend_small)
    draw.text(
        (etat_x + (sq - etat_tw) // 2, legend_y + sq + 4 * scale),
        etat_label,
        fill=COLOR_LABEL,
        font=font_legend_small,
    )

    draw.text(
        (etat_x + sq + 12 * scale, legend_y + (sq - less_h) // 2),
        more_label,
        fill=COLOR_LABEL,
        font=font_legend,
    )

    if scale > 1:
        img = img.resize((width // scale, height // scale), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def build_emoji_grid(stats: dict) -> str:
    today = stats["today"]
    days: List[date] = stats["days"]
    start = days[0]
    active_lookup = {day: flag for day, flag in zip(days, stats["active_flags"])}
    grid_start = start - timedelta(days=start.weekday())
    num_weeks = ((today - grid_start).days // 7) + 1

    lines = []
    for row, label in enumerate(WEEKDAY_LABELS):
        cells = []
        for week in range(num_weeks):
            day = grid_start + timedelta(days=week * 7 + row)
            if day < start or day > today:
                cells.append("▪️")
            elif active_lookup.get(day):
                cells.append("🟩")
            else:
                cells.append("⬛")
        lines.append(f"{label}  {''.join(cells)}")
    return "\n".join(lines)


def build_embed(member: discord.Member, stats: dict) -> discord.Embed:
    start = stats["days"][0]
    end = stats["today"]
    active_count = stats["active_count"]
    color = discord.Color.from_rgb(57, 211, 83) if active_count else discord.Color.from_rgb(110, 118, 129)

    embed = discord.Embed(
        title=f"Aktywność — {member.display_name}",
        description=(
            f"{format_date_pl(start)} – {format_date_pl(end)}\n"
            f"**{active_count} / {WINDOW_DAYS}** dni z aktywnością"
        ),
        color=color,
        timestamp=now_warsaw(),
    )
    embed.add_field(
        name="🔥 Aktualna seria",
        value=f"**{stats['current_streak']}** {dni_label(stats['current_streak'])}",
        inline=True,
    )
    embed.add_field(
        name="🏆 Najdłuższa seria",
        value=f"**{stats['longest_streak']}** {dni_label(stats['longest_streak'])}",
        inline=True,
    )
    embed.set_footer(text="Im jaśniejsza zieleń, tym więcej czasu na VC · ostatnie 30 dni")
    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)
    return embed


@tasks.loop(minutes=COMMIT_INTERVAL_MINUTES)
async def commit_daily_voice():
    if not active_voice_sessions:
        return

    now = time.time()
    guild = CLIENT_REF.get_guild(GUILD_ID) if CLIENT_REF and GUILD_ID else None

    with _file_lock:
        data = load_activity()
        changed = reconcile_daily_voice_sessions(guild, now, data)

        for user_id, start_ts in list(active_voice_sessions.items()):
            member = get_member_in_voice(guild, user_id) if guild else None
            if member is None or not is_voice_countable(member.voice, user_id):
                if flush_daily_voice_session(user_id, now, data) > 0:
                    changed = True
                continue

            for day, seconds in iter_session_chunks(start_ts, now):
                add_seconds(data, user_id, day, seconds)
            active_voice_sessions[user_id] = now
            changed = True

        if changed:
            save_activity(data)


def apply_daily_voice_session(member: discord.Member, now: float) -> None:
    user_id = member.id
    should_count = is_voice_countable(member.voice, member.id)

    if should_count:
        if user_id not in active_voice_sessions:
            active_voice_sessions[user_id] = now
        return

    flush_daily_voice_session(user_id, now)


def _scan_current_voice(guild: Optional[discord.Guild]) -> None:
    if guild is None:
        return
    now = time.time()
    channels = list(guild.voice_channels) + list(getattr(guild, "stage_channels", []))
    for channel in channels:
        for member in channel.members:
            if member.bot or not member.voice:
                continue
            apply_daily_voice_session(member, now)


async def setup_aktywnosc_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int):
    global CLIENT_REF, GUILD_ID
    CLIENT_REF = client
    GUILD_ID = guild_id
    guild_obj = discord.Object(id=guild_id)

    async def listener_on_voice_state_update(
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot or member.guild is None or member.guild.id != guild_id:
            return

        now = time.time()
        apply_daily_voice_session(member, now)

        seen_ids = {member.id}
        for affected in iter_affected_voice_members(before, after):
            if affected.id in seen_ids:
                continue
            seen_ids.add(affected.id)
            apply_daily_voice_session(affected, now)

    client.add_listener(listener_on_voice_state_update, "on_voice_state_update")

    if not commit_daily_voice.is_running():
        commit_daily_voice.start()

    _scan_current_voice(client.get_guild(guild_id))

    @tree.command(
        name="aktywnosc",
        description="Pokazuje aktywność na kanałach głosowych z ostatnich 30 dni",
        guild=guild_obj,
    )
    @app_commands.describe(nick="Użytkownik (puste = Twoja aktywność)")
    async def aktywnosc(interaction: discord.Interaction, nick: Optional[discord.Member] = None):
        await interaction.response.defer()

        target = nick or interaction.user
        if not isinstance(target, discord.Member):
            guild = interaction.guild or client.get_guild(guild_id)
            target = guild.get_member(target.id) if guild else None
            if target is None:
                await interaction.followup.send(
                    "Nie znaleziono tego użytkownika na serwerze.",
                    ephemeral=True,
                )
                return

        if target.bot:
            await interaction.followup.send("Boty nie są śledzone.", ephemeral=True)
            return

        now = time.time()
        guild = interaction.guild or client.get_guild(guild_id)
        with _file_lock:
            data = load_activity()
            if reconcile_daily_voice_sessions(guild, now, data):
                save_activity(data)

        stats = compute_stats(seconds_by_day_for_user(target.id))
        embed = build_embed(target, stats)

        try:
            buffer = await asyncio.to_thread(build_heatmap_image, stats)
            file = discord.File(fp=buffer, filename="aktywnosc.png")
            embed.set_image(url="attachment://aktywnosc.png")
            await interaction.followup.send(embed=embed, file=file)
        except discord.NotFound:
            print("[aktywnosc] Interakcja wygasła zanim zdążyła wyjść odpowiedź.")
        except Exception as exc:
            print(f"[aktywnosc] Nie udało się wygenerować heatmapy: {exc}")
            embed.description = f"{embed.description}\n\n{build_emoji_grid(stats)}"
            try:
                await interaction.followup.send(embed=embed)
            except discord.NotFound:
                print("[aktywnosc] Interakcja wygasła zanim zdążyła wyjść odpowiedź.")
