from typing import TypedDict


class MemoryState(TypedDict):
    messages: list
    user_profile: dict
    episodes: list
    semantic_hits: list[str]
    memory_budget: int


def make_initial_state(memory_budget: int = 2000) -> MemoryState:
    return MemoryState(
        messages=[],
        user_profile={},
        episodes=[],
        semantic_hits=[],
        memory_budget=memory_budget,
    )