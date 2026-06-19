import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import discord
import requests
from discord import app_commands
from discord.ext import tasks

from daily_guard import (
    already_sent_today,
    is_within_send_window,
    mark_sent_today,
    today_str,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = PROJECT_ROOT / "txt"
API_KEY_FILE = TXT_DIR / "youtube_api_key.txt"
CONFIG_FILE = TXT_DIR / "youtube_shorts.json"
STATE_FILE = TXT_DIR / "youtube_shorts_state.json"

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
}
CONSENT_COOKIES = {"CONSENT": "YES+1"}
DAILY_EMBED_MARKER = "YouTube Shorts"

CLIENT_REF: Optional[discord.Client] = None


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[YT Shorts] Failed to read {path}: {e}")
    return default


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[YT Shorts] Failed to write {path}: {e}")


def load_api_key() -> Optional[str]:
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception as e:
        print(f"[YT Shorts] Failed to read API key: {e}")
    return None


def load_config() -> Dict[str, Any]:
    return _load_json(CONFIG_FILE, {})


def load_state() -> Dict[str, Any]:
    return _load_json(STATE_FILE, {})


def save_state(data: Dict[str, Any]) -> None:
    _save_json(STATE_FILE, data)


def _extract_channel_id_from_html(html_text: str) -> Optional[str]:
    patterns = [
        r'"channelId"\s*:\s*"(UC[\w-]+)"',
        r'"browseId"\s*:\s*"(UC[\w-]+)"',
        r"youtube\.com/channel/(UC[\w-]+)",
    ]
    for pat in patterns:
        match = re.search(pat, html_text)
        if match:
            return match.group(1)
    return None


def _extract_handle_from_url(youtube_url: str) -> Optional[str]:
    match = re.search(r"youtube\.com/@([\w.-]+)", youtube_url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def resolve_channel_id(youtube_url: str, api_key: Optional[str] = None) -> Optional[str]:
    match = re.search(r"youtube\.com/(?:channel/)(UC[\w-]+)", youtube_url)
    if match:
        return match.group(1)

    handle = _extract_handle_from_url(youtube_url)
    if handle and api_key:
        try:
            data = _api_get(
                "channels",
                {"part": "id", "forHandle": handle},
                api_key,
            )
            items = data.get("items", [])
            if items:
                return items[0]["id"]
        except Exception as e:
            print(f"[YT Shorts] API resolve failed for @{handle}: {e}")

    candidate_urls = [
        youtube_url,
        youtube_url.rstrip("/") + "/about",
        youtube_url.rstrip("/") + "/videos",
    ]
    for url in candidate_urls:
        try:
            resp = requests.get(url, headers=USER_AGENT, cookies=CONSENT_COOKIES, timeout=20)
            resp.raise_for_status()
            channel_id = _extract_channel_id_from_html(resp.text)
            if channel_id:
                return channel_id
        except Exception as e:
            print(f"[YT Shorts] Resolve attempt failed for {url}: {e}")
    return None


def _api_get(endpoint: str, params: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    query = dict(params)
    query["key"] = api_key
    resp = requests.get(f"{YOUTUBE_API_BASE}/{endpoint}", params=query, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        message = data["error"].get("message", "Unknown YouTube API error")
        raise RuntimeError(message)
    return data


def _parse_iso8601_duration(duration: str) -> int:
    if not duration or not duration.startswith("PT"):
        return 0
    hours = minutes = seconds = 0
    for value, unit in re.findall(r"(\d+)([HMS])", duration):
        num = int(value)
        if unit == "H":
            hours = num
        elif unit == "M":
            minutes = num
        elif unit == "S":
            seconds = num
    return hours * 3600 + minutes * 60 + seconds


def format_views(count: int) -> str:
    return f"{count:,}".replace(",", " ")


def format_delta(delta: int) -> str:
    if delta > 0:
        return f"+{format_views(delta)}"
    if delta < 0:
        return f"-{format_views(abs(delta))}"
    return "0"


def _prune_snapshots(snapshots: Dict[str, Any], keep_days: int = 30) -> None:
    if len(snapshots) <= keep_days:
        return
    for date_str in sorted(snapshots.keys())[:-keep_days]:
        del snapshots[date_str]


def find_previous_snapshot(snapshots: Dict[str, Any], before_date: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    older_dates = sorted(date_str for date_str in snapshots if date_str < before_date)
    if not older_dates:
        return None
    prev_date = older_dates[-1]
    return prev_date, snapshots[prev_date]


def save_daily_snapshot(stats: Dict[str, Any], date_str: str) -> None:
    state = load_state()
    snapshots = state.setdefault("snapshots", {})
    snapshots[date_str] = {
        "total_views": stats["total_views"],
        "videos": {
            video["video_id"]: {"views": video["views"], "title": video["title"]}
            for video in stats["videos"]
        },
    }
    _prune_snapshots(snapshots)
    save_state(state)


def apply_daily_comparison(stats: Dict[str, Any], reference_date: Optional[str] = None) -> Dict[str, Any]:
    state = load_state()
    snapshots = state.get("snapshots", {})
    today_str = reference_date or datetime.now().strftime("%Y-%m-%d")

    previous = find_previous_snapshot(snapshots, today_str)
    if not previous:
        stats["comparison"] = None
        stats["top_3_growth"] = []
        stats["total_views_delta"] = None
        return stats

    prev_date, prev_data = previous
    prev_views_map = {
        video_id: video["views"]
        for video_id, video in prev_data.get("videos", {}).items()
    }

    for video in stats["videos"]:
        prev_views = prev_views_map.get(video["video_id"])
        if prev_views is None:
            video["views_delta"] = video["views"]
            video["is_new"] = True
        else:
            video["views_delta"] = video["views"] - prev_views
            video["is_new"] = False

    stats["total_views_delta"] = sum(video["views_delta"] for video in stats["videos"])
    stats["top_3_growth"] = sorted(
        stats["videos"],
        key=lambda video: video["views_delta"],
        reverse=True,
    )[:3]
    stats["comparison"] = {"previous_date": prev_date}
    return stats


def _is_short_video(video: Dict[str, Any], max_seconds: int = 60) -> bool:
    duration = video.get("contentDetails", {}).get("duration", "")
    return 0 < _parse_iso8601_duration(duration) <= max_seconds


def get_uploads_playlist_id(channel_id: str, api_key: str) -> Tuple[str, str]:
    data = _api_get(
        "channels",
        {"part": "contentDetails,snippet", "id": channel_id},
        api_key,
    )
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"Nie znaleziono kanału YouTube: {channel_id}")
    channel = items[0]
    uploads_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    channel_title = channel.get("snippet", {}).get("title", "YouTube")
    return uploads_id, channel_title


def get_recent_videos(
    uploads_playlist_id: str,
    api_key: str,
    limit: int = 20,
    shorts_only: bool = False,
) -> List[Dict[str, Any]]:
    playlist_data = _api_get(
        "playlistItems",
        {
            "part": "snippet",
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        },
        api_key,
    )
    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in playlist_data.get("items", [])
        if item.get("snippet", {}).get("resourceId", {}).get("videoId")
    ]
    if not video_ids:
        return []

    videos_data = _api_get(
        "videos",
        {"part": "statistics,snippet,contentDetails", "id": ",".join(video_ids)},
        api_key,
    )
    videos = videos_data.get("items", [])
    videos.sort(
        key=lambda v: v.get("snippet", {}).get("publishedAt", ""),
        reverse=True,
    )

    if shorts_only:
        videos = [video for video in videos if _is_short_video(video)]

    result = []
    for video in videos[:limit]:
        snippet = video.get("snippet", {})
        stats = video.get("statistics", {})
        result.append(
            {
                "video_id": video["id"],
                "title": snippet.get("title", "Bez tytułu"),
                "url": f"https://www.youtube.com/shorts/{video['id']}",
                "views": int(stats.get("viewCount", 0)),
                "published_at": snippet.get("publishedAt"),
            }
        )
    return result


def fetch_shorts_stats(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or load_config()
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError("Brak klucza API. Utwórz plik txt/youtube_api_key.txt")

    youtube_url = config.get("youtube_url")
    if not youtube_url:
        raise RuntimeError("Brak youtube_url w txt/youtube_shorts.json")

    channel_id = config.get("channel_id")
    if not channel_id:
        state = load_state()
        channel_id = state.get("resolved_channel_id")
    if not channel_id:
        channel_id = resolve_channel_id(youtube_url, api_key=api_key)
    if not channel_id:
        raise RuntimeError(f"Nie udało się ustalić channel_id dla {youtube_url}")

    state = load_state()
    state["resolved_channel_id"] = channel_id
    save_state(state)

    limit = int(config.get("video_count", 20))
    shorts_only = bool(config.get("shorts_only", False))

    uploads_playlist_id, channel_title = get_uploads_playlist_id(channel_id, api_key)
    videos = get_recent_videos(
        uploads_playlist_id,
        api_key,
        limit=limit,
        shorts_only=shorts_only,
    )
    if not videos:
        raise RuntimeError("Nie znaleziono filmów na kanale.")

    total_views = sum(video["views"] for video in videos)

    return {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "channel_url": youtube_url,
        "video_count": len(videos),
        "total_views": total_views,
        "videos": videos,
    }


def fetch_shorts_stats_with_comparison(
    config: Optional[Dict[str, Any]] = None,
    reference_date: Optional[str] = None,
) -> Dict[str, Any]:
    stats = fetch_shorts_stats(config)
    return apply_daily_comparison(stats, reference_date=reference_date)


def build_stats_embed(stats: Dict[str, Any]) -> discord.Embed:
    comparison = stats.get("comparison")
    total_delta = stats.get("total_views_delta")

    if comparison and total_delta is not None:
        prev_date = datetime.strptime(comparison["previous_date"], "%Y-%m-%d").strftime("%d.%m.%Y")
        total_value = (
            f"**{format_views(stats['total_views'])}** łącznie\n"
            f"**{format_delta(total_delta)}** od {prev_date}"
        )
    else:
        total_value = (
            f"**{format_views(stats['total_views'])}** łącznie\n"
            "_Pierwszy pomiar — jutro pojawi się porównanie doby._"
        )

    medals = ["🥇", "🥈", "🥉"]
    growth_lines = []
    for index, video in enumerate(stats.get("top_3_growth", [])):
        medal = medals[index] if index < len(medals) else f"{index + 1}."
        title = video["title"]
        if len(title) > 70:
            title = title[:67] + "..."
        new_badge = " 🆕" if video.get("is_new") else ""
        growth_lines.append(
            f"{medal} [{title}]({video['url']}){new_badge}\n"
            f"　**{format_delta(video['views_delta'])}** "
            f"_(łącznie {format_views(video['views'])})_"
        )

    embed = discord.Embed(
        title="📊 YouTube Shorts — statystyki dobowe",
        description=(
            f"Kanał: **{stats['channel_title']}**\n"
            f"Ostatnie **{stats['video_count']}** filmów"
        ),
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    embed.add_field(
        name="Wyświetlenia (ostatnie 20)",
        value=total_value,
        inline=False,
    )
    embed.add_field(
        name="Top 3 wzrostu w ciągu doby",
        value="\n".join(growth_lines) if growth_lines else "_Brak danych porównawczych._",
        inline=False,
    )

    thumb_video = stats.get("top_3_growth", [{}])[0] if stats.get("top_3_growth") else stats.get("videos", [{}])[0]
    if thumb_video.get("video_id"):
        embed.set_thumbnail(url=f"https://i.ytimg.com/vi/{thumb_video['video_id']}/hqdefault.jpg")
    embed.set_footer(text="YouTube Data API • porównanie ze snapshotem z poprzedniej doby")
    return embed


async def run_daily_stats_if_due(client: discord.Client) -> None:
    config = load_config()
    channel_id = config.get("discord_channel_id")
    if not channel_id:
        return

    offset_hours = int(config.get("send_offset_hours", 0))
    today = today_str(offset_hours)
    send_hour = int(config.get("send_hour", 9))
    window_hours = int(config.get("send_window_hours", 2))

    state = load_state()
    if await already_sent_today(
        client,
        int(channel_id),
        DAILY_EMBED_MARKER,
        state,
        save_state,
        offset_hours=offset_hours,
    ):
        return

    if not is_within_send_window(send_hour, window_hours, offset_hours):
        return

    try:
        stats = fetch_shorts_stats_with_comparison(config, reference_date=today)
    except Exception as e:
        print(f"[YT Shorts] Daily fetch failed: {e}")
        return

    channel = client.get_channel(int(channel_id))
    if not channel:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            channel = None
    if not channel:
        print(f"[YT Shorts] Cannot find Discord channel {channel_id}")
        return

    embed = build_stats_embed(stats)
    try:
        await channel.send(embed=embed)
        print(f"[YT Shorts] Posted daily stats to #{channel_id}")
    except Exception as e:
        print(f"[YT Shorts] Failed to post daily stats: {e}")
        return

    save_daily_snapshot(stats, today)
    state = load_state()
    state["last_run_date"] = today
    save_state(state)


@tasks.loop(minutes=30)
async def track_daily_shorts_stats():
    if not CLIENT_REF or not CLIENT_REF.is_ready():
        return
    await run_daily_stats_if_due(CLIENT_REF)


async def setup_youtube_shorts(
    client: discord.Client,
    tree: app_commands.CommandTree,
    guild_id: int = None,
) -> None:
    global CLIENT_REF
    CLIENT_REF = client
    guild = discord.Object(id=guild_id) if guild_id else None

    @tree.command(
        name="ytshorts",
        description="Statystyki YouTube Shorts z porównaniem do poprzedniej doby",
        guild=guild,
    )
    async def ytshorts(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            stats = fetch_shorts_stats_with_comparison()
            embed = build_stats_embed(stats)
            await interaction.followup.send(embed=embed)

            config = load_config()
            daily_channel_id = config.get("discord_channel_id")
            offset_hours = int(config.get("send_offset_hours", 0))
            if daily_channel_id and interaction.channel_id == int(daily_channel_id):
                state = load_state()
                mark_sent_today(state, save_state, offset_hours=offset_hours)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    if load_api_key() and load_config().get("youtube_url"):
        if not track_daily_shorts_stats.is_running():
            track_daily_shorts_stats.start()
        print("[YT Shorts] Module ready.")
    else:
        print("[YT Shorts] Missing API key or config — slash command only.")


def _print_cli_summary(stats: Dict[str, Any]) -> None:
    print(f"\nKanał: {stats['channel_title']}")
    print(f"Łącznie wyświetleń (20 ostatnich): {format_views(stats['total_views'])}")

    if stats.get("comparison") and stats.get("total_views_delta") is not None:
        prev_date = stats["comparison"]["previous_date"]
        print(f"Wzrost od {prev_date}: {format_delta(stats['total_views_delta'])}")
        print("\nTop 3 wzrostu w ciągu doby:")
        for index, video in enumerate(stats.get("top_3_growth", []), start=1):
            new_tag = " [NOWY]" if video.get("is_new") else ""
            print(
                f"  {index}. {video['title']}{new_tag} — "
                f"{format_delta(video['views_delta'])} (łącznie {format_views(video['views'])})"
            )
            print(f"     {video['url']}")
    else:
        print("\nBrak snapshotu z poprzedniej doby — uruchom jutro lub poczekaj na codzienny raport.")


if __name__ == "__main__":
    try:
        stats = fetch_shorts_stats_with_comparison()
        _print_cli_summary(stats)
    except Exception as exc:
        print(f"Błąd: {exc}")
