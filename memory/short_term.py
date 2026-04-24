class ShortTermMemory:
    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self._buffer: list[dict] = []

    def add(self, role: str, content: str) -> None:
        self._buffer.append({"role": role, "content": content})
        self._buffer = self._buffer[-(self.max_turns * 2):]

    def get_recent(self) -> list[dict]:
        return self._buffer.copy()

    def clear(self) -> None:
        self._buffer.clear()