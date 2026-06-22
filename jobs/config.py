import json
from pathlib import Path
from typing import Any, Dict

from jobs.constants import DEFAULT_CONFIG

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = PROJECT_ROOT / "txt"
CONFIG_FILE = TXT_DIR / "jobs_watch.json"
STATE_FILE = TXT_DIR / "jobs_state.json"

_config: Dict[str, Any] = {}


def load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Jobs] Failed to read {path}: {e}")
    return default


def save_json(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Jobs] Failed to write {path}: {e}")


def load_config() -> Dict[str, Any]:
    global _config
    stored = load_json(CONFIG_FILE, None)
    if not stored:
        _config = json.loads(json.dumps(DEFAULT_CONFIG))
        save_json(CONFIG_FILE, _config)
        return _config

    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update({k: v for k, v in stored.items() if k != "filters"})
    merged["filters"] = {**DEFAULT_CONFIG["filters"], **stored.get("filters", {})}
    _config = merged
    return _config


def save_config(config: Dict[str, Any]):
    global _config
    _config = config
    save_json(CONFIG_FILE, config)


def filter_signature(filters: Dict[str, Any]) -> str:
    return json.dumps(filters, sort_keys=True, ensure_ascii=False)
