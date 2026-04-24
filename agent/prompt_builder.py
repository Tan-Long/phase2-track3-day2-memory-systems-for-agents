from agent.state import MemoryState


def build_prompt(state: MemoryState) -> str:
    parts = []

    profile = state.get("user_profile", {})
    if profile:
        lines = [f"- {k}: {v}" for k, v in profile.items()]
        parts.append("## User Profile\n" + "\n".join(lines))

    episodes = state.get("episodes", [])
    if episodes:
        lines = [f"- {e.get('task', '')}: {e.get('outcome', '')}" for e in episodes[:3]]
        parts.append("## Past Episodes\n" + "\n".join(lines))

    semantic_hits = state.get("semantic_hits", [])
    if semantic_hits:
        parts.append("## Relevant Knowledge\n" + "\n".join(semantic_hits[:3]))

    messages = state.get("messages", [])
    if messages:
        lines = [f"{m['role']}: {m['content']}" for m in messages]
        parts.append("## Recent Conversation\n" + "\n".join(lines))

    prompt = "\n\n".join(parts)

    budget = state.get("memory_budget", 2000)
    prompt = _trim_to_budget(prompt, budget, profile)

    return prompt


def _trim_to_budget(prompt: str, budget: int, profile: dict) -> str:
    if len(prompt) <= budget:
        return prompt

    sections = prompt.split("\n\n")
    profile_text = ""
    other_sections = []

    for section in sections:
        if section.startswith("## User Profile"):
            profile_text = section
        else:
            other_sections.append(section)

    result_parts = [profile_text] if profile_text else []
    remaining = budget - (len(profile_text) + 2 if profile_text else 0)

    for section in reversed(other_sections):
        if remaining <= 0:
            break
        if len(section) + 2 <= remaining:
            result_parts.insert(1 if profile_text else 0, section)
            remaining -= len(section) + 2

    return "\n\n".join(result_parts)