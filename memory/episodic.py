import json
from pathlib import Path
from datetime import datetime


class EpisodicMemory:
    def __init__(self, path: str = "data/episodes.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._episodes: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            with open(self.path, "r") as f:
                content = f.read().strip()
                if content:
                    self._episodes = json.loads(content)
                else:
                    self._episodes = []
        else:
            self._episodes = []

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._episodes, f, indent=2)

    def add(self, task: str, outcome: str) -> None:
        entry = {
            "task": task,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat(),
        }
        self._episodes.append(entry)
        self._save()

    def search(self, keyword: str, top_k: int = 3) -> list[dict]:
        keyword_lower = keyword.lower()
        scored = []
        for ep in self._episodes:
            text = f"{ep.get('task', '')} {ep.get('outcome', '')}".lower()
            if keyword_lower in text:
                scored.append(ep)
        return scored[:top_k]