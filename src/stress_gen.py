"""
stress_gen.py
Generates the 3 large testcases for each question block — purely in code.

No LLM involvement. Claude writes TC1-TC7; this module overwrites TC8, TC9
and TC10 with large deterministic inputs and computes their expected output
by running the question's own Python reference solution.

TC8-TC10 always get three distinct lengths. At least 2 of them push close to
the upper length constraint by keeping most elements small (so the line still
fits an Excel cell) while pinning a handful of elements to the true val_lo/
val_hi — not the whole array. The remaining testcase uses the true value
range across every element, which naturally caps its length lower.

Supported input shape (v2):
    line 1: n
    line 2: n space-separated integers
    line 3+: zero or more extra scalars (e.g. a target), one per line

Blocks whose TC1 does not match that shape are left untouched.
"""

import re
import random

from src.executor import _run_python

# Excel hard-caps a cell at 32,767 characters. Stay clear of the edge.
CELL_CHAR_BUDGET = 30_000

# Even at 1 digit per element ("d "), a line can't hold more than this many
# elements — an absolute ceiling regardless of the problem's own max length.
HARD_CAP_LEN = CELL_CHAR_BUDGET // 2

# How many elements get pinned to the true val_lo / val_hi in a near-max
# length testcase — "a few", not the whole array.
BOUNDARY_TOUCHES = 3

# Fallbacks used only when the constraints block cannot be parsed.
DEFAULT_MAX_LEN = 10_000
DEFAULT_VAL_LO  = -1000
DEFAULT_VAL_HI  = 1000

# Fixed seeds -> identical sheets on every regeneration.
SEEDS = (20240001, 20240002, 20240003)

_SUP_CHARS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_MAP   = str.maketrans(_SUP_CHARS, "0123456789")


def _normalize_exponents(text: str) -> str:
    """
    Claude's own generated markdown doesn't always write '10^9' or '10**9'.
    Normalize the common alternatives to a plain '10^9' form so the rest of
    the parsing below only has to handle one notation. This normalized copy
    is used only for constraint parsing — the actual question text is never
    touched.
      '10<sup>9</sup>' (HTML superscript, what this project's prompt uses)
      '10⁹'            (unicode superscript digits)
      '$10^9$'         (LaTeX-style math delimiters)
      '10^{9}'         (LaTeX-style braces)
      '10 ^ 9'         (stray spacing around the caret)
      '`nums[i]`'      (backticked identifiers)
    """
    text = re.sub(r"<sup>\s*(\d+)\s*</sup>", r"^\1", text, flags=re.IGNORECASE)
    text = text.replace("`", "")
    text = re.sub(
        rf"(\d)([{_SUP_CHARS}]+)",
        lambda m: m.group(1) + "^" + m.group(2).translate(_SUP_MAP),
        text,
    )
    text = text.replace("$", "")
    text = re.sub(r"\^\s*\{\s*(\d+)\s*\}", r"^\1", text)
    text = re.sub(r"\s*\^\s*", "^", text)
    return text


# ── Constraint parsing ────────────────────────────────────────────────────────

def _expand_power(token: str) -> int:
    """
    '104'   -> 10000   (LeetCode markdown drops the superscript on 10^4)
    '10^5'  -> 100000
    '10**9' -> 1000000000   (Python-style exponent, common in pasted text)
    '2**31' -> 2147483648
    '1e4'   -> 10000
    '5000'  -> 5000
    """
    token = token.strip().replace(",", "").replace(" ", "")
    m = re.fullmatch(r"(\d+)(?:\^|\*\*)(\d+)", token)
    if m:
        return int(m.group(1)) ** int(m.group(2))
    m = re.fullmatch(r"(\d+)e(\d+)", token, re.IGNORECASE)
    if m:
        return int(m.group(1)) * (10 ** int(m.group(2)))
    if re.fullmatch(r"10\d", token):          # 103, 104, 105 ...
        return 10 ** int(token[2:])
    if re.fullmatch(r"\d+", token):
        return int(token)
    raise ValueError(token)


def parse_constraints(question_md: str) -> tuple:
    """
    Pull (max_len, val_lo, val_hi) out of the problem's Constraints block.
    Falls back to defaults for anything it cannot find.
    """
    text = _normalize_exponents(question_md or "")

    max_len = DEFAULT_MAX_LEN
    m = re.search(
        r"(?:length|size|n)\s*(?:<=|≤|\\leq|\\le)\s*([0-9^*e,]+)", text, re.IGNORECASE
    )
    if m:
        try:
            max_len = _expand_power(m.group(1))
        except ValueError:
            pass

    val_lo, val_hi = DEFAULT_VAL_LO, DEFAULT_VAL_HI
    m = re.search(
        r"(-?[0-9^*e,]+)\s*(?:<=|≤|\\leq|\\le)\s*\w+\s*\[\s*\w+\s*\]\s*(?:<=|≤|\\leq|\\le)\s*(-?[0-9^*e,]+)",
        text,
    )
    if m:
        try:
            lo_raw, hi_raw = m.group(1), m.group(2)
            val_lo = -_expand_power(lo_raw.lstrip("-")) if lo_raw.startswith("-") \
                else _expand_power(lo_raw)
            val_hi = -_expand_power(hi_raw.lstrip("-")) if hi_raw.startswith("-") \
                else _expand_power(hi_raw)
        except ValueError:
            pass

    if val_hi < val_lo:
        val_lo, val_hi = val_hi, val_lo
    return max_len, val_lo, val_hi


def parse_scalar_bounds(question_md: str) -> list:
    """
    Generic '(-)lo <= name <= (-)hi' constraints for plain scalar variables
    (target, k, x, ...) — NOT array elements or the length/size bound, which
    are already handled by parse_constraints. Returned in the order they
    appear in the text, to be matched positionally against extra input lines.
    """
    text = _normalize_exponents(question_md or "")
    bounds = []
    pattern = re.compile(
        r"(-?[0-9^*e,]+)\s*(?:<=|≤|\\leq|\\le)\s*([A-Za-z_]\w*)\s*(?:<=|≤|\\leq|\\le)\s*(-?[0-9^*e,]+)"
    )
    for lo_raw, name, hi_raw in pattern.findall(text):
        if name.lower() in ("length", "size", "n"):
            continue
        try:
            lo = -_expand_power(lo_raw.lstrip("-")) if lo_raw.startswith("-") \
                else _expand_power(lo_raw)
            hi = -_expand_power(hi_raw.lstrip("-")) if hi_raw.startswith("-") \
                else _expand_power(hi_raw)
        except ValueError:
            continue
        if hi < lo:
            lo, hi = hi, lo
        bounds.append((lo, hi))
    return bounds


def cell_safe_length(max_len: int, val_lo: int, val_hi: int) -> int:
    """
    Largest n whose serialised array still fits inside one Excel cell.
    Width per element = widest value's digits + sign + separator.
    """
    width = max(len(str(val_lo)), len(str(val_hi))) + 1
    return max(1, min(max_len, CELL_CHAR_BUDGET // width))


# ── Generic array strategies ──────────────────────────────────────────────────
# Deliberately problem-agnostic: the expected output always comes from running
# the reference solution, so these never need to know what is being asked.

def _random_full(n, lo, hi, rng):
    return [rng.randint(lo, hi) for _ in range(n)]


def _extremes(n, lo, hi, rng):
    return [rng.choice((lo, hi)) for _ in range(n)]


def _sorted_ascending(n, lo, hi, rng):
    return sorted(rng.randint(lo, hi) for _ in range(n))


def _all_max(n, lo, hi, rng):
    return [hi] * n


def _mostly_uniform(n, lo, hi, rng):
    """Long run of one value with a few outliers — hits early-exit paths."""
    arr = [hi] * n
    for _ in range(max(1, n // 100)):
        arr[rng.randrange(n)] = lo
    return arr


STRATEGIES = [
    ("random_full",      _random_full),
    ("extremes",         _extremes),
    ("sorted_ascending", _sorted_ascending),
    ("mostly_uniform",   _mostly_uniform),
    ("all_max",          _all_max),
]


# ── Near-upper-bound sizing for the last testcases ────────────────────────────

def _near_max_sizes(effective_max: int, count: int) -> list:
    """
    `count` distinct sizes drawn from the top ~20% of [1, effective_max].
    Falls back to the largest distinct sizes available (max, max-1, max-2, ...)
    when the constraint is too small for that band to hold `count` values.
    """
    effective_max = max(1, effective_max)
    band_lo = max(1, int(effective_max * 0.8))
    band = list(range(band_lo, effective_max + 1))

    if len(band) >= count:
        rng = random.Random(SEEDS[0])
        return sorted(rng.sample(band, count), reverse=True)

    sizes = list(range(effective_max, 0, -1))[:count]
    while len(sizes) < count:
        sizes.append(sizes[-1])
    return sizes


def _touch_extremes(arr: list, lo, hi, rng, count: int = 1) -> list:
    """Pin a handful of elements to the true boundary values — not the whole array."""
    n = len(arr)
    if not arr or lo == hi:
        return arr
    if n == 1:
        arr[0] = rng.choice((lo, hi))
        return arr
    count = max(1, min(count, n // 2))
    idxs  = rng.sample(range(n), 2 * count)
    for k, idx in enumerate(idxs):
        arr[idx] = hi if k < count else lo
    return arr


def _bulk_value_range(n: int, extreme_touches: int, lo: int, hi: int) -> tuple:
    """
    Small sub-range for the BULK of a near-max-length array so the whole
    line still fits in one Excel cell — the true lo/hi still get pinned onto
    a handful of elements afterwards via _touch_extremes.
    """
    if hi - lo <= 20:                      # range is already tiny, nothing to shrink
        return lo, hi
    extreme_width = max(len(str(lo)), len(str(hi))) + 1
    reserved       = 2 * extreme_touches * extreme_width + 20   # + slack for n/target lines
    budget         = max(n, CELL_CHAR_BUDGET - reserved)
    per_elem       = max(2, budget // max(1, n))
    digits         = max(1, per_elem - 2)          # reserve 1 for sign, 1 for separator
    cap            = 10 ** digits - 1
    small_hi = min(hi, cap)
    small_lo = max(lo, -cap)
    if small_lo >= small_hi:
        return lo, hi
    return small_lo, small_hi


# ── Shape detection ───────────────────────────────────────────────────────────

def detect_shape(tc_input: str):
    """
    Returns the number of trailing scalar lines (0, 1, 2, ...) if tc_input
    matches: line 1 = n, line 2 = n space-separated ints, remaining lines
    (if any) = one integer each (target, k, x, ...). Returns None if the
    input doesn't match this shape at all.
    """
    lines = [ln for ln in (tc_input or "").strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    try:
        n    = int(lines[0].strip())
        vals = [int(t) for t in lines[1].split()]
    except ValueError:
        return None
    if n != len(vals) or n <= 0:
        return None
    for ln in lines[2:]:
        try:
            int(ln.strip())
        except ValueError:
            return None
    return len(lines) - 2


def _format_input(arr: list, scalars: list = None) -> str:
    parts = [str(len(arr)), " ".join(map(str, arr))]
    if scalars:
        parts.extend(str(s) for s in scalars)
    return "\n".join(parts)


def _generate_scalars(arr, count, bounds_list, arr_lo, arr_hi, rng, attempt):
    """
    One value per extra scalar line. Different heuristics per attempt so a
    failed guess (e.g. no pair in arr sums to a random target) can be retried
    without throwing away the whole array:
      attempt 0 -> sum of two array elements (covers target-style scalars)
      attempt 1 -> an existing array element (covers "value x is in array")
      attempt 2+ -> a random value within the scalar's own parsed range
    """
    scalars = []
    for k in range(count):
        s_lo, s_hi = bounds_list[k] if k < len(bounds_list) else (arr_lo, arr_hi)
        if attempt == 0 and len(arr) >= 2:
            a, b = rng.randrange(len(arr)), rng.randrange(len(arr))
            val = arr[a] + arr[b]
        elif attempt == 1 and arr:
            val = rng.choice(arr)
        else:
            val = rng.randint(s_lo, s_hi)
        scalars.append(val)
    return scalars


# ── Main entry point ──────────────────────────────────────────────────────────

def inject_stress_testcases(rows: list, count: int = 3, timeout: int = 25) -> tuple:
    """
    Overwrite the last `count` testcase rows of every question block with
    large generated cases.

    Returns (rows, injected_count, skipped_blocks).
    """
    injected = 0
    skipped  = 0

    i = 0
    while i < len(rows):
        row = rows[i]
        if not isinstance(row, dict):
            i += 1
            continue

        is_block_start = (
            row.get("Code_language") == "PYTHON"
            and row.get("Question Content (in Markdown)", "").strip()
        )
        if not is_block_start:
            i += 1
            continue

        solution = row.get("Solution Code", "").strip()
        if not solution:
            i += 1
            continue

        # TC1 lives on the JAVA row (i+1) — use it to detect the input shape.
        sample = ""
        if i + 1 < len(rows) and isinstance(rows[i + 1], dict):
            sample = rows[i + 1].get("Test_case_input", "")

        extra_count = detect_shape(sample)
        if extra_count is None:
            skipped += 1
            i += 1
            continue

        max_len, lo, hi = parse_constraints(
            row.get("Question Content (in Markdown)", "")
        )
        scalar_bounds = (
            parse_scalar_bounds(row.get("Question Content (in Markdown)", ""))
            if extra_count else []
        )

        # At least `count - 1` slots push close to the true length limit
        # (mostly-small elements + a few pinned boundary values). The one
        # remaining slot uses the true value range across every element,
        # which naturally caps it lower — genuine full-magnitude diversity.
        near_max_slots = max(0, count - 1)
        near_ceiling    = min(max_len, HARD_CAP_LEN)
        near_sizes      = _near_max_sizes(near_ceiling, near_max_slots)

        effective_max  = cell_safe_length(max_len, lo, hi)
        moderate_size  = _near_max_sizes(effective_max, 1)[0]

        sizes = near_sizes + [moderate_size]
        seen  = set()
        for k in range(len(sizes)):                      # keep all sizes distinct
            while sizes[k] in seen and sizes[k] > 1:
                sizes[k] -= 1
            seen.add(sizes[k])

        # Last `count` testcase rows in this block: offsets 10, 9, 8 ...
        target_offsets = list(range(11 - count, 11))

        for slot, offset in enumerate(target_offsets):
            idx = i + offset
            if idx >= len(rows) or not isinstance(rows[idx], dict):
                continue

            name, fn   = STRATEGIES[slot % len(STRATEGIES)]
            rng        = random.Random(SEEDS[slot % len(SEEDS)])
            is_near_max = slot < near_max_slots

            size = sizes[slot % len(sizes)]
            for attempt in range(4):                 # scalar guesses, then shrink
                if is_near_max:
                    small_lo, small_hi = _bulk_value_range(size, BOUNDARY_TOUCHES, lo, hi)
                    arr = fn(size, small_lo, small_hi, rng)
                    arr = _touch_extremes(arr, lo, hi, rng, count=BOUNDARY_TOUCHES)
                else:
                    arr = fn(size, lo, hi, rng)
                    arr = _touch_extremes(arr, lo, hi, rng)
                if name == "sorted_ascending":
                    arr.sort()

                scalars  = _generate_scalars(arr, extra_count, scalar_bounds, lo, hi, rng, attempt)
                tc_input = _format_input(arr, scalars)
                if len(tc_input) > CELL_CHAR_BUDGET:
                    size = int(size * 0.8)
                    continue
                out = _run_python(solution, tc_input, timeout=timeout)
                if out is not None:
                    rows[idx]["Test_case_input"]  = tc_input
                    rows[idx]["Test_case_output"] = out
                    rows[idx]["Test_case_type"]   = "NORMAL_CASE"
                    injected += 1
                    break
                if attempt >= 2:
                    size = max(100, size // 2)       # solution too slow — back off

        i += 1

    return rows, injected, skipped