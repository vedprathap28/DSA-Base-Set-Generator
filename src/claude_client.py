"""
claude_client.py
Handles all communication with Claude via the OpenRouter gateway.
"""

import os
import json
import re
import unicodedata
import anthropic
from dotenv import load_dotenv
from src.system_prompt import get_system_prompt, get_mode_label
from src.subtopic_parser import build_subtopic_instructions

load_dotenv()

# ── OpenRouter configuration ──────────────────────────────────────────────────
BASE_URL = "https://openrouter.ai/api"
MODEL    = "anthropic/claude-sonnet-4.5"

# Zero-width / non-breaking characters that survive .strip() and break auth.
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u00a0\u2060"), None)

# ── Exact code templates per approach ─────────────────────────────────────────
# These are shown to Claude as REQUIRED patterns to follow, per question.

_BACKTRACKING_TEMPLATE = """
BACKTRACKING TEMPLATE — copy this exact structure, adapt variable names/logic:

PYTHON (mandatory):
```python
def functionName(param):
    n = len(param)
    answer = 0
    def backtrack(index):
        nonlocal answer
        if index == n:
            return
        # track state across index..n
        state1 = 0
        state2 = 0
        for i in range(index, n):
            # update state based on param[i]
            if param[i] == 'X':
                state1 += 1
            else:
                state2 += 1
            # when valid partition found
            if state1 == state2:
                answer += 1
                backtrack(i + 1)  # recurse from next position
                return             # backtrack — stop exploring further
    backtrack(0)
    return answer
```

JAVA (mandatory — use static helper with int[] result):
```java
static int answer = 0;
static void backtrack(String s, int index) {
    if (index == s.length()) return;
    int state1 = 0, state2 = 0;
    for (int i = index; i < s.length(); i++) {
        if (s.charAt(i) == 'X') state1++;
        else state2++;
        if (state1 == state2) {
            answer++;
            backtrack(s, i + 1);
            return;
        }
    }
}
```

CPP (mandatory — pass answer by reference):
```cpp
void backtrack(string& s, int index, int& answer) {
    if (index == (int)s.size()) return;
    int state1 = 0, state2 = 0;
    for (int i = index; i < (int)s.size(); i++) {
        if (s[i] == 'X') state1++;
        else state2++;
        if (state1 == state2) {
            answer++;
            backtrack(s, i + 1, answer);
            return;
        }
    }
}
```

YOU MUST USE THIS RECURSIVE BACKTRACK STRUCTURE. A plain for-loop solution is REJECTED.
"""

_APPROACH_TEMPLATES = {
    "backtracking": _BACKTRACKING_TEMPLATE,
}


def _build_template_block(subtopics: list) -> str:
    """
    For each subtopic that has an explicit template, inject the template
    into the user message so Claude has no excuse to ignore it.
    """
    if not subtopics:
        return ""

    lines = []
    for i, st in enumerate(subtopics, start=1):
        st_clean = st.strip().lower()
        if st_clean in _APPROACH_TEMPLATES:
            lines.append(
                f"\n--- Q{i} MANDATORY CODE TEMPLATE ---"
                f"{_APPROACH_TEMPLATES[st_clean]}"
                f"--- END Q{i} TEMPLATE ---\n"
            )
    return "\n".join(lines)


def clean_key(raw: str) -> str:
    """Normalise a pasted key: strip whitespace, invisible chars and stray quotes."""
    return (
        unicodedata.normalize("NFKC", raw or "")
        .translate(_INVISIBLE)
        .strip()
        .strip("'\"")
    )


def get_client(api_key: str = None) -> anthropic.Anthropic:
    key = clean_key(api_key or os.getenv("OPENROUTER_API_KEY", ""))
    if not key or key == "your_api_key_here":
        raise ValueError(
            "OpenRouter API key not set. Enter it in the app, or add "
            "OPENROUTER_API_KEY to your .env file."
        )
    if not key.startswith("sk-or-"):
        raise ValueError(
            f"That does not look like an OpenRouter key (it starts with "
            f"'{key[:8]}...'). OpenRouter keys begin with 'sk-or-v1-'."
        )
    return anthropic.Anthropic(
        api_key=key,
        base_url=BASE_URL,
        default_headers={"X-Title": "DSA Dataset Generator"},
    )


def extract_json(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw.strip())
        raw = raw.strip()
    start = raw.find("[")
    end   = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "No valid JSON array found in Claude's response.\n\n"
            "First 600 chars:\n" + raw[:600]
        )
    json_str = raw[start : end + 1]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON parse error: {e}\n\nExtracted (first 600 chars):\n{json_str[:600]}"
        )
    if not isinstance(data, list):
        raise ValueError("Claude response is not a JSON array.")
    return data


def generate_rows(
    problem_text: str,
    function_based: bool = False,
    subtopics: list = None,
    api_key: str = None,
) -> list:
    client        = get_client(api_key)
    system_prompt = get_system_prompt(function_based=function_based, subtopics=subtopics or [])
    mode_label    = get_mode_label(function_based)

    subtopic_block  = build_subtopic_instructions(subtopics or [])
    template_block  = _build_template_block(subtopics or [])

    user_message = (
        f"MODE: {mode_label}\n"
        f"{subtopic_block}\n"
        f"{template_block}\n"
        "STRICT INSTRUCTIONS:\n"
        "1. Process each question ONE AT A TIME — fully complete Q1 (all 12 rows) before starting Q2.\n"
        "2. For each question, mentally verify every testcase against the solution before writing it.\n"
        "3. Each question block = exactly 12 rows: PYTHON + JAVA + CPP + 8 overflow rows + 1 blank separator.\n"
        "4. Exactly 10 testcases per question — TC1 on JAVA row, TC2 on CPP row, TC3-TC10 on overflow rows.\n"
        "5. CRITICAL: Where a MANDATORY CODE TEMPLATE is shown above, your Solution Code MUST follow that exact recursive structure. A plain for-loop or greedy solution will be marked as WRONG and rejected.\n"
        "6. Return ONLY a pure JSON array — no markdown, no explanation, no code fences.\n\n"
        f"Problem(s):\n\n{problem_text}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    if not raw_text.strip():
        raise ValueError("Claude returned an empty response.")

    return extract_json(raw_text)