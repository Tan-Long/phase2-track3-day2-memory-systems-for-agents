import json
from pathlib import Path


class SemanticMemory:
    def __init__(self, path: str = "data/knowledge_base.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._chunks: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            with open(self.path, "r") as f:
                self._chunks = json.load(f)
        else:
            self._chunks = []

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._chunks, f, indent=2)

    def add(self, text: str, metadata: dict | None = None) -> None:
        self._chunks.append({"text": text, "metadata": metadata or {}})
        self._save()

    def search(self, keyword: str, top_k: int = 3) -> list[str]:
        keywords = keyword.lower().split()
        scored: list[tuple[int, str]] = []
        for chunk in self._chunks:
            text = chunk.get("text", "").lower()
            title = chunk.get("metadata", {}).get("title", "").lower()
            combined = text + " " + title
            match_count = sum(1 for kw in keywords if kw in combined)
            if match_count > 0:
                scored.append((match_count, chunk.get("text", "")))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_k]]