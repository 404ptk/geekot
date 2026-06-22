import asyncio
import json
import random
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import discord
from discord import app_commands
from discord.ext import tasks
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from daily_guard import (
    already_sent_today,
    is_within_send_window,
    mark_sent_today,
    today_str,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = PROJECT_ROOT / "txt"
CONFIG_FILE = TXT_DIR / "drive_daily.json"
STATE_FILE = TXT_DIR / "drive_daily_state.json"
DEFAULT_SERVICE_ACCOUNT = TXT_DIR / "google_service_account.json"

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"
MAX_DISCORD_BYTES = 25 * 1024 * 1024
DAILY_EMBED_MARKER = "Losowe wspomnienie"
HEIC_EXTENSIONS = {".heic", ".heif"}
HEIC_MIMES = {"image/heic", "image/heif", "image/heif-sequence"}
ACCEPTED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", *HEIC_EXTENSIONS,
}
ACCEPTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}

_heif_registered = False

CLIENT_REF: Optional[discord.Client] = None


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Drive Daily] Failed to read {path}: {e}")
    return default


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Drive Daily] Failed to write {path}: {e}")


def load_config() -> Dict[str, Any]:
    return _load_json(CONFIG_FILE, {})


def load_state() -> Dict[str, Any]:
    return _load_json(STATE_FILE, {"sent_ids": []})


def save_state(data: Dict[str, Any]) -> None:
    _save_json(STATE_FILE, data)


def get_service_account_path(config: Optional[Dict[str, Any]] = None) -> Path:
    config = config or load_config()
    rel_path = config.get("service_account_file", "txt/google_service_account.json")
    return PROJECT_ROOT / rel_path


def build_drive_service(config: Optional[Dict[str, Any]] = None):
    account_path = get_service_account_path(config)
    if not account_path.exists():
        raise RuntimeError(f"Brak pliku service account: {account_path}")

    credentials = service_account.Credentials.from_service_account_file(
        str(account_path),
        scopes=DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def list_folder_children(service, folder_id: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return items


def has_acceptable_extension(file_item: Dict[str, Any]) -> bool:
    suffix = Path(file_item.get("name", "")).suffix.lower()
    if not suffix:
        return False

    mime = file_item.get("mimeType", "")
    if mime.startswith("image/"):
        return suffix in ACCEPTED_IMAGE_EXTENSIONS
    if mime.startswith("video/"):
        return suffix in ACCEPTED_VIDEO_EXTENSIONS
    return False


def is_eligible_media(file_item: Dict[str, Any], sent_ids: Set[str]) -> bool:
    if file_item["id"] in sent_ids:
        return False

    mime = file_item.get("mimeType", "")
    if not (mime.startswith("image/") or mime.startswith("video/")):
        return False

    if not has_acceptable_extension(file_item):
        return False

    size_raw = file_item.get("size")
    if size_raw is not None:
        size = int(size_raw)
        if size > MAX_DISCORD_BYTES:
            return False
        if mime.startswith("video/") and size <= 0:
            return False

    if mime.startswith("video/") and size_raw is None:
        return False

    return True


def _random_walk_pick(
    service,
    folder_id: str,
    sent_ids: Set[str],
    depth: int = 0,
    max_depth: int = 20,
) -> Optional[Dict[str, Any]]:
    if depth > max_depth:
        return None

    children = list_folder_children(service, folder_id)
    folders = [item for item in children if item.get("mimeType") == FOLDER_MIME]
    files = [item for item in children if is_eligible_media(item, sent_ids)]

    random.shuffle(folders)
    random.shuffle(files)

    if not folders and not files:
        return None

    if files and folders:
        explore_folder = random.random() < 0.6
    elif folders:
        explore_folder = True
    else:
        return random.choice(files)

    if not explore_folder and files:
        return random.choice(files)

    if folders:
        random.shuffle(folders)
        for folder in folders:
            found = _random_walk_pick(
                service,
                folder["id"],
                sent_ids,
                depth + 1,
                max_depth,
            )
            if found:
                return found

    if files:
        return random.choice(files)

    return None


def collect_all_media(
    service,
    folder_id: str,
    sent_ids: Set[str],
) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    stack = [folder_id]
    visited_folders: Set[str] = set()

    while stack:
        current = stack.pop()
        if current in visited_folders:
            continue
        visited_folders.add(current)

        children = list_folder_children(service, current)
        subfolders = [item for item in children if item.get("mimeType") == FOLDER_MIME]
        random.shuffle(subfolders)

        for item in children:
            if is_eligible_media(item, sent_ids):
                found.append(item)

        for folder in subfolders:
            stack.append(folder["id"])

    return found


def pick_random_media(
    service,
    root_folder_id: str,
    sent_ids: Set[str],
    walk_attempts: int = 40,
) -> Optional[Dict[str, Any]]:
    for _ in range(walk_attempts):
        picked = _random_walk_pick(service, root_folder_id, sent_ids)
        if picked:
            return picked

    candidates = collect_all_media(service, root_folder_id, sent_ids)
    if not candidates:
        return None
    return random.choice(candidates)


def download_drive_file(service, file_id: str, destination: Path) -> None:
    request = service.files().get_media(fileId=file_id)
    with open(destination, "wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _ensure_heif_support() -> None:
    global _heif_registered
    if _heif_registered:
        return
    import pillow_heif

    pillow_heif.register_heif_opener()
    _heif_registered = True


def is_heic_file(path: Path, mime_type: str = "") -> bool:
    if path.suffix.lower() in HEIC_EXTENSIONS:
        return True
    return mime_type.lower().split(";")[0].strip() in HEIC_MIMES


def convert_heic_for_discord(path: Path, original_name: str) -> Tuple[Path, str]:
    _ensure_heif_support()
    from PIL import Image

    jpg_path = path.with_suffix(".jpg")
    with Image.open(path) as img:
        img.convert("RGB").save(jpg_path, "JPEG", quality=92, optimize=True)

    path.unlink(missing_ok=True)
    jpg_name = f"{Path(original_name).stem}.jpg"

    if jpg_path.stat().st_size > MAX_DISCORD_BYTES:
        jpg_path.unlink(missing_ok=True)
        raise RuntimeError(f"Plik {original_name} po konwersji przekracza limit Discord.")

    return jpg_path, jpg_name


def prepare_file_for_discord(
    path: Path,
    mime_type: str,
    original_name: str,
) -> Tuple[Path, str, bool]:
    if is_heic_file(path, mime_type):
        new_path, new_name = convert_heic_for_discord(path, original_name)
        return new_path, new_name, True
    return path, original_name, False


def prepare_random_post(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or load_config()
    folder_id = config.get("folder_id")
    if not folder_id:
        raise RuntimeError("Brak folder_id w txt/drive_daily.json")

    service = build_drive_service(config)
    state = load_state()
    sent_ids = set(state.get("sent_ids", []))
    reset_pool = False

    picked = pick_random_media(service, folder_id, sent_ids)
    if not picked:
        sent_ids.clear()
        reset_pool = True
        picked = pick_random_media(service, folder_id, sent_ids)

    if not picked:
        raise RuntimeError("Nie znaleziono żadnych zdjęć ani nagrań w folderze.")

    suffix = Path(picked["name"]).suffix.lower()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(temp_file.name)
    temp_file.close()

    mime = picked.get("mimeType", "")
    try:
        download_drive_file(service, picked["id"], temp_path)
        temp_path, discord_filename, converted_from_heic = prepare_file_for_discord(
            temp_path,
            mime,
            picked["name"],
        )
        file_size = temp_path.stat().st_size
        if file_size > MAX_DISCORD_BYTES:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Plik {picked['name']} ma {file_size // (1024 * 1024)} MB — powyżej limitu Discord."
            )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return {
        "file_id": picked["id"],
        "name": picked["name"],
        "discord_filename": discord_filename,
        "mime_type": mime,
        "is_video": mime.startswith("video/"),
        "converted_from_heic": converted_from_heic,
        "local_path": temp_path,
        "reset_pool": reset_pool,
    }


def build_memory_embed(post: Dict[str, Any]) -> discord.Embed:
    description = f"**{post['name']}**"
    if post.get("converted_from_heic"):
        description += "\n_(HEIC → JPG, żeby Discord wyświetlił podgląd)_"
    if post.get("reset_pool"):
        description += "\n_Kolekcja się skończyła — losujemy od nowa._"

    return discord.Embed(
        title=f"📸 Losowe wspomnienie",
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.now(),
    )


async def send_random_memory(
    client: discord.Client,
    channel_id: int,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    post = await loop.run_in_executor(None, prepare_random_post, config)

    channel = client.get_channel(channel_id)
    if not channel:
        channel = await client.fetch_channel(channel_id)

    embed = build_memory_embed(post)
    discord_filename = post.get("discord_filename", post["name"])
    try:
        await channel.send(
            embed=embed,
            file=discord.File(str(post["local_path"]), filename=discord_filename),
        )
    finally:
        post["local_path"].unlink(missing_ok=True)

    state = load_state()
    sent_ids = state.setdefault("sent_ids", [])
    if post["file_id"] not in sent_ids:
        sent_ids.append(post["file_id"])

    config = config or load_config()
    daily_channel_id = config.get("discord_channel_id")
    offset_hours = int(config.get("send_offset_hours", 0))
    if daily_channel_id and int(channel_id) == int(daily_channel_id):
        mark_sent_today(state, save_state, offset_hours=offset_hours)
    else:
        save_state(state)

    return post


async def run_daily_memory_if_due(client: discord.Client) -> None:
    config = load_config()
    channel_id = config.get("discord_channel_id")
    if not channel_id:
        return

    offset_hours = int(config.get("send_offset_hours", 0))
    today = today_str(offset_hours)
    send_hour = int(config.get("send_hour", 10))
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
        await send_random_memory(client, int(channel_id), config)
        print(f"[Drive Daily] Posted random memory to #{channel_id}")
    except Exception as e:
        print(f"[Drive Daily] Daily post failed: {e}")
        return

    state = load_state()
    state["last_run_date"] = today
    save_state(state)


@tasks.loop(minutes=30)
async def track_daily_drive_memory():
    if not CLIENT_REF or not CLIENT_REF.is_ready():
        return
    await run_daily_memory_if_due(CLIENT_REF)


async def setup_drive_daily(
    client: discord.Client,
    tree: app_commands.CommandTree,
    guild_id: int = None,
) -> None:
    global CLIENT_REF
    CLIENT_REF = client
    guild = discord.Object(id=guild_id) if guild_id else None

    @tree.command(
        name="wspomnienie",
        description="Losuje i wysyła zdjęcie lub nagranie z Google Drive",
        guild=guild,
    )
    async def wspomnienie(interaction: discord.Interaction):
        await interaction.response.defer()
        config = load_config()
        channel_id = config.get("discord_channel_id") or interaction.channel_id
        try:
            post = await send_random_memory(client, int(channel_id), config)
            if interaction.channel_id != int(channel_id):
                await interaction.followup.send(
                    f"✅ Wysłano **{post['name']}** na <#{channel_id}>.",
                    ephemeral=True,
                )
            else:
                await interaction.delete_original_response()
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    account_path = get_service_account_path()
    if account_path.exists() and load_config().get("folder_id"):
        if not track_daily_drive_memory.is_running():
            track_daily_drive_memory.start()
        print("[Drive Daily] Module ready.")
    else:
        print("[Drive Daily] Missing service account or config — slash command only.")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    try:
        post = prepare_random_post()
        print(f"Wylosowano: {post['name']}")
        print(f"Typ: {'wideo' if post['is_video'] else 'zdjęcie'}")
        print(f"Rozmiar: {post['local_path'].stat().st_size // 1024} KB")
        if post.get("reset_pool"):
            print("Uwaga: pula została zresetowana (wszystko już było wysłane).")
        if not dry_run:
            print("\nUżyj --dry-run żeby tylko sprawdzić losowanie bez wysyłki na Discord.")
        post["local_path"].unlink(missing_ok=True)
    except Exception as exc:
        print(f"Błąd: {exc}")
