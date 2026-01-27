import json, os, time
from typing import Any, Dict

DB_PATH = os.getenv("DB_PATH", "db.json")

def _load() -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"users": {}, "paper": {}, "live": {}, "logs": []}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: Dict[str, Any]) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(uid: int) -> Dict[str, Any]:
    data = _load()
    u = data["users"].get(str(uid), {})
    return u

def set_user(uid: int, updates: Dict[str, Any]) -> None:
    data = _load()
    u = data["users"].get(str(uid), {})
    u.update(updates)
    data["users"][str(uid)] = u
    _save(data)

def log_event(evt: Dict[str, Any]) -> None:
    data = _load()
    evt["ts"] = int(time.time())
    data["logs"].append(evt)
    data["logs"] = data["logs"][-1000:]
    _save(data)

def paper_get(uid: int) -> Dict[str, Any]:
    data = _load()
    return data["paper"].get(str(uid), {"balance": 1000.0, "positions": []})

def paper_set(uid: int, val: Dict[str, Any]) -> None:
    data = _load()
    data["paper"][str(uid)] = val
    _save(data)

def live_get(uid: int) -> Dict[str, Any]:
    data = _load()
    return data["live"].get(str(uid), {"enabled": False, "exchange": None})

def live_set(uid: int, val: Dict[str, Any]) -> None:
    data = _load()
    data["live"][str(uid)] = val
    _save(data)
