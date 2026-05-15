"""
subtopic_parser.py
Parses free-text subtopic input and maps to problem indices.
Injects subtopics into the correct PYTHON rows in the generated row list.

Input format (one per line, positional):
    two_pointers
    bit_manipulation
    sliding_window

Maps line 1 → problem 1, line 2 → problem 2, etc.
Extra subtopics (beyond number of problems) are ignored.
Missing subtopics → Sub_Topics column stays empty for that problem.
"""

# Subtopics that drive solution approach (passed to Claude in prompt)
APPROACH_DRIVEN = {
    "two_pointers",
    "sliding_window",
    "bit_manipulation",
    "recursion",
    "backtracking",
    "dynamic_programming",
}

# Normalisation map — handle common variations
_NORMALISE = {
    "two_pointer":        "two_pointers",
    "twopointers":        "two_pointers",
    "two pointer":        "two_pointers",
    "two pointers":       "two_pointers",
    "slidingwindow":      "sliding_window",
    "sliding window":     "sliding_window",
    "bitmask":            "bit_manipulation",
    "bitmanipulation":    "bit_manipulation",
    "bit manipulation":   "bit_manipulation",
    "dp":                 "dynamic_programming",
    "dynamicprogramming": "dynamic_programming",
    "dynamic programming":"dynamic_programming",
    "backtrack":          "backtracking",
    "recurse":            "recursion",
    "recursive":          "recursion",
    "array":              "arrays",
    "string":             "strings",
}


def parse_subtopics(raw_text: str) -> list:
    """
    Parse free-text subtopic input into a list of normalised subtopic strings.
    One subtopic per line. Returns list positionally mapped to problems.

    e.g. "two_pointers\\nbit_manipulation\\n" → ["two_pointers", "bit_manipulation"]
    Empty/blank lines produce "" (no subtopic for that problem).
    """
    import re
    lines = raw_text.strip().splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        # Strip leading number prefix: "1 - ", "1. ", "1) ", "2 - " etc.
        stripped = re.sub(r'^\d+\s*[-.):\s]\s*', '', stripped).strip()
        # Lowercase, replace spaces and hyphens with underscore
        cleaned = stripped.lower().replace(" ", "_").replace("-", "_").strip("_")
        # Normalise common variations
        normalised = _NORMALISE.get(cleaned, cleaned)
        result.append(normalised)
    return result


def format_for_xlsx(subtopic: str) -> str:
    """
    Convert subtopic to CAPS format for xlsx Sub_Topics column.
    e.g. "two_pointers" → "TWO_POINTERS"
    """
    return subtopic.upper() if subtopic else ""


def inject_subtopics(rows: list, subtopics: list) -> list:
    """
    Walk through rows, find PYTHON rows (start of each question block),
    and inject the corresponding subtopic into Sub_Topics column.

    Args:
        rows:      List of row dicts from Claude (already executor-corrected)
        subtopics: List of subtopic strings, positionally mapped to questions

    Returns:
        Updated rows list with Sub_Topics filled in PYTHON rows
    """
    question_index = 0  # which problem we're on

    for row in rows:
        if not isinstance(row, dict):
            continue
        if (
            row.get("Code_language") == "PYTHON"
            and row.get("Question Content (in Markdown)", "").strip()
        ):
            if question_index < len(subtopics):
                subtopic = subtopics[question_index]
                row["Sub_Topics"] = format_for_xlsx(subtopic)
            # else: leave Sub_Topics empty (already "")
            question_index += 1

    return rows


def build_subtopic_instructions(subtopics: list) -> str:
    """
    Build the subtopic instruction block to inject into the Claude user message.
    Tells Claude which approach to use per question.

    Returns empty string if no approach-driven subtopics.
    """
    if not subtopics:
        return ""

    lines = []
    for i, st in enumerate(subtopics, start=1):
        if st in APPROACH_DRIVEN:
            friendly = st.replace("_", " ").title()
            lines.append(f"  Q{i}: Solve using {friendly} approach.")
        elif st:
            lines.append(f"  Q{i}: Use simplest, most readable solution (subtopic: {st}).")
        else:
            lines.append(f"  Q{i}: Use simplest, most readable solution.")

    if not lines:
        return ""

    return (
        "\nSUBTOPIC INSTRUCTIONS — follow exactly for each question:\n"
        + "\n".join(lines)
        + "\n"
    )