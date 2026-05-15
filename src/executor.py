"""
executor.py
Runs Claude-generated Python solutions against testcases using subprocess.
Auto-corrects wrong testcase outputs silently before xlsx generation.
"""

import subprocess
import sys
import tempfile
import os
from typing import List, Dict


def _run_python(code: str, stdin_input: str, timeout: int = 10) -> str:
    """
    Execute Python code with given stdin and return stdout output (stripped).
    Returns None if execution fails or times out.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            input=stdin_input,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        output = result.stdout.strip()
        return output if output else None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def verify_and_fix_testcases(rows: list) -> tuple:
    """
    For each question block:
      1. Find the PYTHON row and extract solution code
      2. Find all testcase rows (JAVA, CPP, overflow)
      3. Run each testcase through the Python solution
      4. Auto-correct any wrong outputs silently

    Args:
        rows: List of row dicts from Claude

    Returns:
        (corrected_rows, correction_count)
    """
    corrections = 0

    # ── Identify question blocks ──────────────────────────────────────────────
    # A block starts at a PYTHON row with Question Content filled
    i = 0
    while i < len(rows):
        row = rows[i]
        if not isinstance(row, dict):
            i += 1
            continue

        # Start of a question block
        if row.get("Code_language") == "PYTHON" and row.get("Question Content (in Markdown)", "").strip():
            python_solution = row.get("Solution Code", "").strip()

            if not python_solution:
                i += 1
                continue

            # Collect testcase rows in this block:
            # JAVA row = i+1, CPP row = i+2, overflow = i+3 to i+10
            tc_row_indices = []
            for offset in range(1, 11):  # rows i+1 through i+10
                if i + offset < len(rows):
                    tc_row_indices.append(i + offset)

            for tc_idx in tc_row_indices:
                tc_row = rows[tc_idx]
                if not isinstance(tc_row, dict):
                    continue

                tc_input  = tc_row.get("Test_case_input", "")
                tc_output = tc_row.get("Test_case_output", "")
                tc_type   = tc_row.get("Test_case_type", "")

                # Only process rows that have testcase data
                if not tc_input or not tc_type:
                    continue

                # Run the solution
                actual_output = _run_python(python_solution, tc_input)

                if actual_output is None:
                    # Execution failed — leave as is
                    continue

                if actual_output != str(tc_output).strip():
                    # Auto-correct silently
                    rows[tc_idx]["Test_case_output"] = actual_output
                    corrections += 1

            # Skip past this block
            i += 12
        else:
            i += 1

    return rows, corrections