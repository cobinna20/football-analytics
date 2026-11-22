# Cache = notebook
# We save answers here so we don't ask the internet again and again

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

class DiskCache:
    def __init__(self, base_dir, default_ttl=3600):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _path_for(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()
        return self.base_dir / f"{h}.json"

    def get(self, key: str) -> Optional[Any]:
        p = self._path_for(key)
        if not p.exists():
            return None
        try:
            payload = json.loads(p.read_text())
            if time.time() - payload["cached_at"] > payload["ttl"]:
                p.unlink(missing_ok=True)
                return None
            return payload["value"]
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        p = self._path_for(key)
        payload = {"cached_at": time.time(), "ttl": ttl or self.default_ttl, "value": value}
        p.write_text(json.dumps(payload, default=str))

    def clear(self) -> None:
        for f in self.base_dir.glob("*.json"):
            f.unlink(missing_ok=True)
