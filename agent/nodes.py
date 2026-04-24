import re
import json
import urllib.request
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermProfile
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from agent.state import MemoryState

GEMINI_API_KEY = "AIzaSyDZPYnhmRGVQzVNUE257bVpXTjzG0C-4LM"
GEMINI_MODEL = "gemini-2.5-flash"


def retrieve_memory(state: MemoryState, *, stm: ShortTermMemory, ltm: LongTermProfile,
                    episodic: EpisodicMemory, semantic: SemanticMemory) -> MemoryState:
    last_msg = state["messages"][-1] if state["messages"] else {}
    query = last_msg.get("content", "")

    state["user_profile"] = ltm.as_dict()

    episodes = episodic.search(query, top_k=3)
    state["episodes"] = episodes

    semantic_hits = semantic.search(query, top_k=3)
    state["semantic_hits"] = semantic_hits

    return state


def _call_gemini(system_prompt: str, user_message: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {"maxOutputTokens": 512},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["candidates"][0]["content"]["parts"][0]["text"]


def call_llm(state: MemoryState, *, client=None, model: str = GEMINI_MODEL,
             use_api: bool = False) -> MemoryState:
    from agent.prompt_builder import build_prompt
    prompt_text = build_prompt(state)

    messages = state.get("messages", [])
    last_user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break

    if use_api:
        try:
            assistant_content = _call_gemini(prompt_text, last_user_msg)
        except Exception as e:
            assistant_content = f"[API error: {e}]"
    else:
        assistant_content = f"[stub response] Memory-augmented reply based on {len(state.get('user_profile', {}))} profile facts."

    state["messages"].append({"role": "assistant", "content": assistant_content})
    return state


_FACT_PATTERNS = [
    (re.compile(r"my name is\s+(\w+)", re.I), "name"),
    (re.compile(r"i(?:'m| am)\s+(?:allergic to\s+)?(\w[\w\s]*?)(?:\.|,|!|$)", re.I), "allergy"),
    (re.compile(r"i(?:'m| am)\s+allergic to\s+(\w[\w\s]*?)(?:\.|,|!|$)", re.I), "allergy"),
    (re.compile(r"actually,?\s+(?:i(?:'m| am)\s+(?:allergic to\s+)?)(\w[\w\s]*?)(?:\.|,|!|$)", re.I), "allergy"),
    (re.compile(r"i prefer\s+(\w[\w\s]*?)(?:\.|,|!|$)", re.I), "preference"),
    (re.compile(r"i am\s+(\d+)\s+years?\s+old", re.I), "age"),
]


def save_memory(state: MemoryState, *, stm: ShortTermMemory, ltm: LongTermProfile,
                 episodic: EpisodicMemory) -> MemoryState:
    for msg in state.get("messages", []):
        if msg["role"] == "user":
            stm.add(msg["role"], msg["content"])
            content = msg["content"]
            for pattern, key in _FACT_PATTERNS:
                m = pattern.search(content)
                if m:
                    ltm.set(key, m.group(1).strip())

    all_msgs = state.get("messages", [])
    user_msgs = [m for m in all_msgs if m["role"] == "user"]
    assistant_msgs = [m for m in all_msgs if m["role"] == "assistant"]

    if user_msgs and assistant_msgs:
        task = user_msgs[-1]["content"][:100]
        outcome = assistant_msgs[-1]["content"][:100]
        episodic.add(task=task, outcome=outcome)

    return state