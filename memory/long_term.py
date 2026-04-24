import json
from pathlib import Path


class LongTermProfile:
    def __init__(self, path: str = "data/profile.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            with open(self.path, "r") as f:
                self._data = json.load(f)

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._save()

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key, default)

    def as_dict(self) -> dict:
        return self._data.copy()

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._save()