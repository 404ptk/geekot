import time
from typing import Optional, Set

STARTUP_FREEZE_MINUTES = 30

_started_at: Optional[float] = None
_skip_logged: Set[str] = set()
_end_logged: Set[str] = set()


def mark_bot_started() -> None:
    global _started_at
    _started_at = time.monotonic()
    print(f"[Startup] Freeze {STARTUP_FREEZE_MINUTES} min — bez ofert pracy i updateów CS2")


def startup_freeze_remaining_seconds() -> float:
    if _started_at is None:
        return float(STARTUP_FREEZE_MINUTES * 60)
    remaining = (STARTUP_FREEZE_MINUTES * 60) - (time.monotonic() - _started_at)
    return max(0.0, remaining)


def is_startup_freeze_active() -> bool:
    return startup_freeze_remaining_seconds() > 0


def allow_background_api(label: str) -> bool:
    """False during startup freeze — caller should skip API calls and posting."""
    if not is_startup_freeze_active():
        if label in _skip_logged and label not in _end_logged:
            print(f"[Startup] Freeze zakończony — aktywne: {label}")
            _end_logged.add(label)
        return True

    if label not in _skip_logged:
        remaining_min = int(startup_freeze_remaining_seconds() // 60) + 1
        print(f"[Startup] Freeze (~{remaining_min} min): pominięto {label}")
        _skip_logged.add(label)
    return False
