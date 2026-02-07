import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

import discord
import requests
import html  # Unescape HTML entities

# RSS feed template for YouTube channels
YOUTUBE_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
}
# Bypass cookie wall
CONSENT_COOKIES = {"CONSENT": "YES+1"}

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = PROJECT_ROOT / "txt"
CONFIG_FILE = TXT_DIR / "youtube_watch.json"
STATE_FILE = TXT_DIR / "youtube_state.json"

# Keep references to running tasks to prevent GC
_running_tasks = []


def _load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[YouTube] Failed to read {path}: {e}")
    return default


def _save_json(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[YouTube] Failed to write {path}: {e}")


def _extract_channel_id_from_html(html: str) -> Optional[str]:
    # Try common patterns present in the initial data
    patterns = [
        r'"channelId"\s*:\s*"(UC[\w-]+)"',
        r'"browseId"\s*:\s*"(UC[\w-]+)"',
        r'youtube\.com/channel/(UC[\w-]+)'
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def _resolve_channel_id_from_url(youtube_url: str) -> Optional[str]:
    # Accept full channel URL with UC..., or handle @name
    m = re.search(r"youtube\.com/(?:channel/)(UC[\w-]+)", youtube_url)
    if m:
        return m.group(1)

    # Try multiple channel subpages to avoid sparse HTML
    candidate_urls = [
        youtube_url,
        youtube_url.rstrip("/") + "/about",
        youtube_url.rstrip("/") + "/videos",
    ]
    for url in candidate_urls:
        try:
            resp = requests.get(url, headers=USER_AGENT, cookies=CONSENT_COOKIES, timeout=20)
            resp.raise_for_status()
            cid = _extract_channel_id_from_html(resp.text)
            if cid:
                return cid
        except Exception as e:
            print(f"[YouTube] Resolve attempt failed for {url}: {e}")

    print(f"[YouTube] Could not resolve channelId from {youtube_url}. If this persists, add 'channel_id' in txt/youtube_watch.json.")
    return None


def _parse_feed_latest(feed_xml: str) -> Optional[Dict[str, Any]]:
    # Simple and robust parse using regex to avoid adding deps
    entry_match = re.search(r"<entry>(.*?)</entry>", feed_xml, flags=re.DOTALL)
    if not entry_match:
        return None
    entry = entry_match.group(1)

    def tag(tag_name: str, ns: Optional[str] = None):
        if ns:
            return re.search(fr"<{ns}:{tag_name}>(.*?)</{ns}:{tag_name}>", entry, flags=re.DOTALL)
        return re.search(fr"<{tag_name}>(.*?)</{tag_name}>", entry, flags=re.DOTALL)

    m_vid = tag("videoId", ns="yt")
    m_title = tag("title")
    m_author = re.search(r"<author>.*?<name>(.*?)</name>.*?</author>", entry, flags=re.DOTALL)
    m_published = re.search(r"<published>(.*?)</published>", entry)
    m_link = re.search(r"<link[^>]+href=\"(.*?)\"", entry)
    m_desc = re.search(r"<media:description[^>]*>(.*?)</media:description>", entry, flags=re.DOTALL)

    if not m_vid:
        return None
    video_id = m_vid.group(1)
    raw_title = m_title.group(1) if m_title else "Nowy film"
    title = html.unescape(raw_title)
    author = m_author.group(1) if m_author else "YouTube"
    url = m_link.group(1) if m_link else f"https://www.youtube.com/watch?v={video_id}"
    published = m_published.group(1) if m_published else None
    thumb = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

    raw_desc = m_desc.group(1) if m_desc else ""
    desc_text = html.unescape(raw_desc)
    lines = [ln.strip() for ln in desc_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln]
    desc_excerpt = "\n".join(lines[:6]) if lines else ""
    if len(desc_excerpt) > 1024:
        desc_excerpt = desc_excerpt[:1021] + "..."

    return {
        "video_id": video_id,
        "title": title,
        "author": author,
        "url": url,
        "published": published,
        "thumb": thumb,
        "desc_excerpt": desc_excerpt,
    }


async def _check_and_post(client: discord.Client, watcher: Dict[str, Any]):
    state = _load_json(STATE_FILE, {})

    youtube_url = watcher.get("youtube_url")
    discord_channel_id = int(watcher.get("discord_channel_id"))

    # Prefer explicit channel_id from config if provided
    channel_id = watcher.get("channel_id")

    # Else from state cache, else resolve
    if not channel_id:
        channel_id = state.get("resolved", {}).get(youtube_url)
    if not channel_id:
        channel_id = _resolve_channel_id_from_url(youtube_url)
        if not channel_id:
            return
        state.setdefault("resolved", {})[youtube_url] = channel_id
        _save_json(STATE_FILE, state)

    try:
        feed_url = YOUTUBE_FEED_URL.format(channel_id=channel_id)
        resp = requests.get(feed_url, headers=USER_AGENT, timeout=15)
        resp.raise_for_status()
        latest = _parse_feed_latest(resp.text)
        if not latest:
            print(f"[YouTube] No entries for {youtube_url}")
            return
    except Exception as e:
        print(f"[YouTube] Feed error {youtube_url}: {e}")
        return

    last_by_channel = state.setdefault("last", {})
    last_video_id = last_by_channel.get(channel_id)

    if last_video_id == latest["video_id"]:
        return

    if last_video_id is None:
        last_by_channel[channel_id] = latest["video_id"]
        _save_json(STATE_FILE, state)
        print(f"[YouTube] Initialized state for {youtube_url} -> {latest['video_id']}")
        return

    channel = client.get_channel(discord_channel_id)
    if not channel:
        try:
            channel = await client.fetch_channel(discord_channel_id)
        except Exception:
            channel = None
    if not channel:
        print(f"[YouTube] Cannot find Discord channel {discord_channel_id}")
        return

    embed = discord.Embed(
        title=latest["title"],
        url=latest["url"],
        description=f"Nowy film na kanale {latest['author']}",
        color=discord.Color.red(),
    )
    if latest.get("desc_excerpt"):
        embed.add_field(name="Opis", value=latest["desc_excerpt"], inline=False)
    embed.set_image(url=latest["thumb"])  # big preview
    embed.set_footer(text=f"YouTube • {latest['author']}")

    try:
        await channel.send(embed=embed)
        print(f"[YouTube] Posted new video {latest['video_id']} to #{discord_channel_id}")
    except Exception as e:
        print(f"[YouTube] Failed to post to Discord: {e}")
        return

    last_by_channel[channel_id] = latest["video_id"]
    _save_json(STATE_FILE, state)


async def _watcher_worker(client: discord.Client, watcher: Dict[str, Any]):
    interval_hours = float(watcher.get("interval_hours", 2))
    await asyncio.sleep(5)
    while True:
        await _check_and_post(client, watcher)
        await asyncio.sleep(max(300, int(interval_hours * 3600)))


async def setup_youtube_watch(client: discord.Client, tree: discord.app_commands.CommandTree, guild_id: int = None):
    config = _load_json(CONFIG_FILE, [])
    if not config:
        print("[YouTube] No youtube_watch.json config found or it's empty. Skipping watcher setup.")
        return

    for watcher in config:
        task = asyncio.create_task(_watcher_worker(client, watcher))
        _running_tasks.append(task)
        print(f"[YouTube] Watcher started for {watcher.get('youtube_url')} -> {watcher.get('discord_channel_id')}")
