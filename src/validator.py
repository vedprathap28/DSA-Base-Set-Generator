"""
validator.py
Validates the parsed JSON rows from Claude before xlsx generation.
Returns (is_valid: bool, messages: list[str]).
Critical errors block generation. Warnings are shown but don't block.
"""

from typing import Tuple, List

# Must match exactly what Claude is instructed to return
REQUIRED_KEYS = [
    "S. No",
    "Difficulty",
    "Question Content (in Markdown)",
    "Question_short_text",
    "Sub_Topics",
    "Code_language",
    "Solution Code",
    "Front_Code_language",
    "Prefilled Code For Each Code Language",
    "Test_case_input",
    "Test_case_output",
    "Test_case_type",
    "Code_language ",   # trailing space — col 13
    "Backend Code",
]

ALWAYS_EMPTY_KEYS = {"S. No", "Difficulty", "Sub_Topics", "Code_language "}

VALID_LANGUAGES   = {"PYTHON", "JAVA", "CPP"}
INVALID_LANGUAGES = {"NODEJS", "NODE", "NODE.JS", "NODE_JS"}


def validate_rows(rows: list, function_based: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate the row list returned by Claude.

    Returns:
        (is_valid, messages) — is_valid=False means critical error; block download.
    """
    errors   : List[str] = []
    warnings : List[str] = []

    if not rows:
        return False, ["Claude returned zero rows. Nothing to generate."]

    # ── Key presence check (sample first 5 non-blank rows) ───────────────────
    non_blank = [r for r in rows if isinstance(r, dict) and any(r.get(k) for k in REQUIRED_KEYS)]
    sample    = non_blank[:5]

    for idx, row in enumerate(sample):
        missing = [k for k in REQUIRED_KEYS if k not in row]
        if missing:
            errors.append(f"Row {idx+1}: Missing keys — {missing}")

    if errors:
        return False, errors

    # ── Language rows ─────────────────────────────────────────────────────────
    lang_rows = {
        lang: [r for r in non_blank if r.get("Code_language") == lang]
        for lang in VALID_LANGUAGES
    }
    num_questions = len(lang_rows["PYTHON"])

    if num_questions == 0:
        errors.append("No PYTHON language rows found.")
        return False, errors

    for lang in VALID_LANGUAGES:
        count = len(lang_rows[lang])
        if count != num_questions:
            warnings.append(
                f"Expected {num_questions} {lang} rows, found {count}."
            )

    # ── NODEJS check ──────────────────────────────────────────────────────────
    bad_lang = [
        r for r in rows
        if isinstance(r, dict) and r.get("Code_language", "").upper() in INVALID_LANGUAGES
    ]
    if bad_lang:
        errors.append(f"Found {len(bad_lang)} NODEJS row(s) — must be removed.")

    # ── Question content on PYTHON rows only ──────────────────────────────────
    for i, row in enumerate(lang_rows["PYTHON"]):
        if not row.get("Question Content (in Markdown)", "").strip():
            errors.append(f"PYTHON row {i+1}: Question Content is empty.")
        if not row.get("Question_short_text", "").strip():
            warnings.append(f"PYTHON row {i+1}: Question_short_text is empty.")

    # ── PYTHON row testcases must be empty ────────────────────────────────────
    for i, row in enumerate(lang_rows["PYTHON"]):
        if row.get("Test_case_input") or row.get("Test_case_output") or row.get("Test_case_type"):
            warnings.append(
                f"PYTHON row {i+1}: Testcase columns must be empty in PYTHON rows."
            )

    # ── TC1 on JAVA row, TC2 on CPP row ──────────────────────────────────────
    for i, row in enumerate(lang_rows["JAVA"]):
        if not row.get("Test_case_input", "").strip():
            warnings.append(f"JAVA row {i+1}: TC1 Test_case_input is empty.")
        if not row.get("Test_case_output", "").strip():
            warnings.append(f"JAVA row {i+1}: TC1 Test_case_output is empty.")

    for i, row in enumerate(lang_rows["CPP"]):
        if not row.get("Test_case_input", "").strip():
            warnings.append(f"CPP row {i+1}: TC2 Test_case_input is empty.")
        if not row.get("Test_case_output", "").strip():
            warnings.append(f"CPP row {i+1}: TC2 Test_case_output is empty.")

    # ── Always-empty columns ──────────────────────────────────────────────────
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        for key in ALWAYS_EMPTY_KEYS:
            if row.get(key, ""):
                warnings.append(
                    f"Row {idx+1}: '{key}' should be empty but has value."
                )

    # ── Backend Code mode check ───────────────────────────────────────────────
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        lang = row.get("Code_language", "")
        if lang not in VALID_LANGUAGES:
            continue
        backend = row.get("Backend Code", "")
        if function_based and not backend.strip():
            warnings.append(
                f"Row {idx+1} ({lang}): FUNCTION BASED mode — Backend Code should be filled."
            )
        elif not function_based and backend.strip():
            warnings.append(
                f"Row {idx+1} ({lang}): NON-FUNCTION mode — Backend Code should be empty."
            )

    if errors:
        return False, errors + warnings

    return True, warnings
