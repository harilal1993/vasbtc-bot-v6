from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict

DEFAULT_STATE = {
    "balance": 50.0,
    "risk_percent": 1.0,
    "paused": False,
    "last_signal_hash": {},
    "preferred_timeframe": "15m",
    "daily_summary_sent_date": "",
}

class JsonStorage:
    def __init__(self, path: str = "data/state.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self.path.exists():
            self.save(DEFAULT_STATE.copy())

    def load(self) -> Dict[str, Any]:
        with self._lock:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        merged = DEFAULT_STATE.copy()
        merged.update(data)
        return merged

    def save(self, data: Dict[str, Any]) -> None:
        with self._lock:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
