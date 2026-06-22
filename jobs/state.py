from typing import List, Set

from jobs.config import STATE_FILE, load_json, save_json
from jobs.constants import MAX_SEEN_UUIDS


def trim_seen_uuids(seen: Set[str]) -> List[str]:
    if len(seen) <= MAX_SEEN_UUIDS:
        return list(seen)
    return list(seen)[-MAX_SEEN_UUIDS:]


def load_state():
    return load_json(STATE_FILE, {})


def save_state(state):
    save_json(STATE_FILE, state)


def invalidate_state_for_reseed():
    state = load_state()
    state["initialized"] = False
    state["seen_uuids"] = []
    save_state(state)
