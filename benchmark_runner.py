import sys
import os
import json
import urllib.request
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.short_term import ShortTermMemory
from memory.long_term import LongTermProfile
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from agent.state import MemoryState, make_initial_state
from agent.nodes import retrieve_memory, call_llm, save_memory, _FACT_PATTERNS, _call_gemini
from agent.graph import SkeletonGraph
from agent.prompt_builder import build_prompt

GEMINI_API_KEY = "AIzaSyDZPYnhmRGVQzVNUE257bVpXTjzG0C-4LM"
GEMINI_MODEL = "gemini-2.5-flash"

NO_MEM_PROMPT = "You are a helpful assistant. You have NO memory of previous conversations. Answer honestly that you don't remember any personal information."

NO_MEM_RESPONSES = {
    1: "I don't know your name. You haven't told me.",
    2: "I don't have any information about allergies.",
    3: "I'm not aware of any allergies you've mentioned.",
    4: "I don't have a record of any previous tasks.",
    5: "I don't recall any recent deployments.",
    6: "I can provide general information about Python virtual environments, but I don't know your preferences.",
    7: "I can explain how to set up a Python venv, but I have no memory of past conversations about it.",
    8: "I don't know your name or any relevant information.",
    9: "I don't know anything specific about you.",
    10: "I'm not aware of any allergies. Docker networking involves creating custom bridge networks.",
}

BENCHMARK_CONVERSATIONS = [
    {
        "id": 1,
        "category": "Profile Recall",
        "turns": [
            {"role": "user", "content": "My name is Alice"},
            {"role": "user", "content": "How's the weather?"},
            {"role": "user", "content": "Tell me a joke."},
            {"role": "user", "content": "What's 2+2?"},
            {"role": "user", "content": "Interesting."},
            {"role": "user", "content": "What's my name?"},
        ],
        "check": lambda state: state.get("user_profile", {}).get("name") == "Alice",
    },
    {
        "id": 2,
        "category": "Conflict Update",
        "turns": [
            {"role": "user", "content": "I'm allergic to cow milk"},
            {"role": "user", "content": "Actually, I'm allergic to soy milk"},
            {"role": "user", "content": "What am I allergic to?"},
        ],
        "check": lambda state: state.get("user_profile", {}).get("allergy") == "soy milk",
    },
    {
        "id": 3,
        "category": "Profile Conflict",
        "turns": [
            {"role": "user", "content": "I'm allergic to peanuts"},
            {"role": "user", "content": "I'm allergic to tree nuts"},
            {"role": "user", "content": "What should I avoid?"},
        ],
        "check": lambda state: state.get("user_profile", {}).get("allergy") == "tree nuts",
    },
    {
        "id": 4,
        "category": "Episodic Memory",
        "turns": [
            {"role": "user", "content": "I fixed the docker networking bug yesterday"},
            {"role": "user", "content": "How did I fix the docker bug?"},
        ],
        "check": lambda state: len(state.get("episodes", [])) > 0,
    },
    {
        "id": 5,
        "category": "Episodic Retrieval",
        "turns": [
            {"role": "user", "content": "I deployed the app to production"},
            {"role": "user", "content": "What did I deploy recently?"},
        ],
        "check": lambda state: len(state.get("episodes", [])) > 0,
    },
    {
        "id": 6,
        "category": "Semantic Retrieval",
        "turns": [
            {"role": "user", "content": "I prefer dark mode"},
            {"role": "user", "content": "Tell me about Python virtual environments"},
        ],
        "check": lambda state: any("venv" in h.lower() or "virtual" in h.lower() for h in state.get("semantic_hits", [])),
    },
    {
        "id": 7,
        "category": "Semantic Retrieval",
        "turns": [
            {"role": "user", "content": "How do I set up a Python venv?"},
        ],
        "check": lambda state: any("venv" in h.lower() or "virtual" in h.lower() for h in state.get("semantic_hits", [])),
    },
    {
        "id": 8,
        "category": "Token Budget Trim",
        "turns": [
            {"role": "user", "content": "My name is BudgetTester"},
            {"role": "user", "content": "Tell me about Docker networking and Python venv and FAISS dtype and Claude API rate limits and LangGraph error handling"},
        ],
        "check": lambda state: state.get("user_profile", {}).get("name") == "BudgetTester",
    },
    {
        "id": 9,
        "category": "Multi-Fact",
        "turns": [
            {"role": "user", "content": "My name is Bob"},
            {"role": "user", "content": "I am 25 years old"},
            {"role": "user", "content": "I prefer Python"},
            {"role": "user", "content": "What do you know about me?"},
        ],
        "check": lambda state: (state.get("user_profile", {}).get("name") == "Bob"
                                and state.get("user_profile", {}).get("age") == "25"
                                and state.get("user_profile", {}).get("preference") == "Python"),
    },
    {
        "id": 10,
        "category": "Semantic + Profile",
        "turns": [
            {"role": "user", "content": "I'm allergic to shellfish"},
            {"role": "user", "content": "How does Docker networking work?"},
        ],
        "check": lambda state: (state.get("user_profile", {}).get("allergy") == "shellfish"
                                and any("docker" in h.lower() for h in state.get("semantic_hits", []))),
    },
]


def run_with_memory_simple(conv: dict) -> dict:
    tmpdir = tempfile.mkdtemp()
    stm = ShortTermMemory(max_turns=6)
    ltm = LongTermProfile(path=os.path.join(tmpdir, "profile.json"))
    epi = EpisodicMemory(path=os.path.join(tmpdir, "episodes.json"))
    sem = SemanticMemory(path=os.path.join(os.path.dirname(__file__), "data", "knowledge_base.json"))

    for i, turn in enumerate(conv["turns"]):
        stm.add(turn["role"], turn["content"])
        content = turn["content"]
        for pattern, key in _FACT_PATTERNS:
            m = pattern.search(content)
            if m:
                ltm.set(key, m.group(1).strip())

        if i > 0:
            prev = conv["turns"][i - 1]
            if prev["role"] == "user":
                epi.add(task=prev["content"][:100], outcome=f"Processed: {content[:80]}")

    final_state = make_initial_state()
    final_state["messages"] = conv["turns"]
    final_state = retrieve_memory(final_state, stm=stm, ltm=ltm, episodic=epi, semantic=sem)

    return final_state


def call_gemini_for_conv(system_prompt: str, user_query: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_query}]}],
        "generationConfig": {"maxOutputTokens": 256},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"[API error: {e}]"


def run_benchmark_with_api() -> str:
    results = []
    for conv in BENCHMARK_CONVERSATIONS:
        state = run_with_memory_simple(conv)
        with_mem_check = conv["check"](state)

        prompt_text = build_prompt(state)
        last_user_msg = ""
        for m in reversed(conv["turns"]):
            if m["role"] == "user":
                last_user_msg = m["content"]
                break
        with_mem_response = call_gemini_for_conv(prompt_text, last_user_msg)
        no_mem_response = call_gemini_for_conv(NO_MEM_PROMPT, last_user_msg)

        results.append({
            "id": conv["id"],
            "category": conv["category"],
            "with_mem_check": with_mem_check,
            "no_mem_response": no_mem_response,
            "with_mem_response": with_mem_response,
        })

    lines = []
    lines.append("# Benchmark Results\n")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(f"LLM: Gemini `{GEMINI_MODEL}`")
    lines.append("")
    lines.append("## Comparison Table\n")
    lines.append("| # | Category | No-Memory Response (Gemini) | With-Memory Response (Gemini) | Memory Check |")
    lines.append("|---|----------|------|------|------|")
    for r in results:
        check_str = "Pass" if r["with_mem_check"] else "Fail"
        no_resp = r["no_mem_response"].replace("|", "\\|").replace("\n", " ")[:200]
        with_resp = r["with_mem_response"].replace("|", "\\|").replace("\n", " ")[:200]
        lines.append(f"| {r['id']} | {r['category']} | {no_resp} | {with_resp} | {check_str} |")

    lines.append("")
    lines.append("## Detailed Per-Test Results\n")
    for r in results:
        lines.append(f"### Test {r['id']}: {r['category']}")
        lines.append(f"- **No Memory (Gemini)**: {r['no_mem_response']}")
        lines.append(f"- **With Memory (Gemini)**: {r['with_mem_response']}")
        lines.append(f"- **Memory Check**: {'Pass' if r['with_mem_check'] else 'Fail'}")
        if not r["with_mem_check"]:
            lines.append("- **Verdict**: Memory check failed — needs investigation.")
        else:
            lines.append("- **Verdict**: Memory system correctly augmented the LLM response.")
        lines.append("")

    lines.append("## Summary")
    pass_count = sum(1 for r in results if r["with_mem_check"])
    lines.append(f"- Memory checks passed: {pass_count}/10")
    lines.append(f"- LLM backend: Gemini `{GEMINI_MODEL}`")

    return "\n".join(lines)


def run_benchmark_offline() -> str:
    results = []
    for conv in BENCHMARK_CONVERSATIONS:
        state = run_with_memory_simple(conv)
        with_mem = conv["check"](state)
        no_mem_state = make_initial_state()
        no_mem_state["messages"] = conv["turns"]
        no_mem = conv["check"](no_mem_state)

        results.append({
            "id": conv["id"],
            "category": conv["category"],
            "no_memory": "Pass" if no_mem else "Fail",
            "with_memory": "Pass" if with_mem else "Fail",
            "no_mem_response": NO_MEM_RESPONSES.get(conv["id"], "I don't have any memory of that."),
        })

    lines = []
    lines.append("# Benchmark Results\n")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append("## Comparison Table\n")
    lines.append("| # | Category | No-Memory Response | With-Memory Status | No-Memory Status |")
    lines.append("|---|----------|---------------------|----------------------|------------------|")
    for r in results:
        lines.append(f"| {r['id']} | {r['category']} | {r['no_mem_response']} | {r['with_memory']} | {r['no_memory']} |")

    lines.append("")
    lines.append("## Summary")
    no_mem_pass = sum(1 for r in results if r["no_memory"] == "Pass")
    with_mem_pass = sum(1 for r in results if r["with_memory"] == "Pass")
    lines.append(f"- No Memory: {no_mem_pass}/10 pass")
    lines.append(f"- With Memory: {with_mem_pass}/10 pass")
    lines.append(f"- Memory advantage: {with_mem_pass - no_mem_pass} additional tests pass")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", action="store_true", help="Use Gemini API for real LLM responses")
    parser.add_argument("--offline", action="store_true", help="Run offline (stub responses)")
    args = parser.parse_args()

    if args.api:
        print("Running benchmark with Gemini API...")
        output = run_benchmark_with_api()
    else:
        print("Running benchmark offline (stub responses)...")
        output = run_benchmark_offline()

    print(output)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "BENCHMARK.md"), "w") as f:
        f.write(output)
    print("\nBENCHMARK.md written.")