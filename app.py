"""
app.py — DSA Question Dataset Generator
Streamlit web application entry point.
"""

import os
import streamlit as st
import traceback
import anthropic

from src.claude_client import generate_rows
from src.xlsx_generator import rows_to_xlsx
from src.validator import validate_rows
from src.executor import verify_and_fix_testcases
from src.stress_gen import inject_stress_testcases
from src.subtopic_parser import parse_subtopics, inject_subtopics

st.set_page_config(
    page_title="DSA Dataset Generator",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
.stApp { background: #0d1117; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.8rem !important; padding-bottom: 2rem !important; max-width: 820px !important; }

.app-header {
    background: linear-gradient(135deg, #161b27 0%, #1a2035 60%, #0f2a4a 100%);
    border: 1px solid #2a3650;
    border-radius: 14px;
    padding: 32px 40px;
    margin-bottom: 24px;
    text-align: center;
}
.app-header h1 { color: #ffffff; font-size: 1.9rem; font-weight: 700; margin: 0 0 6px 0; }
.app-header p  { color: #cbd5e1; font-size: 0.95rem; margin: 0; }
.badge {
    display: inline-block;
    background: #1e3a5f;
    border: 1px solid #2563eb55;
    color: #60a5fa;
    border-radius: 20px;
    padding: 3px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    margin-bottom: 12px;
}
.sec-label {
    color: #e2e8f0;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.mode-active-pill {
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.82rem;
    margin-bottom: 14px;
    color: #ffffff;
}
.pill-nonfunc { background: #0c1a30; border: 1px solid #1d4ed8; }
.pill-func    { background: #0a1f12; border: 1px solid #15803d; }

.subtopic-box {
    background: #0d1117;
    border: 1px solid #2a3650;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 16px;
}
.subtopic-box p {
    color: #cbd5e1;
    font-size: 0.82rem;
    margin: 0 0 8px 0;
}

.stTextArea textarea {
    background: #0d1117 !important;
    border: 1px solid #2a3650 !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace !important;
    font-size: 0.86rem !important;
}
.stTextArea textarea:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 2px #2563eb22 !important;
}
.stTextArea textarea::placeholder { color: #4a5a70 !important; }
.stTextInput input {
    background: #0d1117 !important;
    border: 1px solid #2a3650 !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace !important;
    font-size: 0.86rem !important;
}

.stButton > button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 12px 28px !important;
    font-size: 0.97rem !important;
    font-weight: 600 !important;
    width: 100% !important;
    transition: all 0.18s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1d4ed8, #1e40af) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px #2563eb40 !important;
}
div[data-testid="column"] .stButton > button[kind="secondary"] {
    background: #161b27 !important;
    border: 1px solid #2a3650 !important;
    color: #cbd5e1 !important;
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #059669, #047857) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 12px 28px !important;
    font-size: 0.97rem !important;
    font-weight: 600 !important;
    width: 100% !important;
    margin-top: 6px !important;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #047857, #065f46) !important;
    transform: translateY(-1px) !important;
}

.box-success {
    background: #041f0f; border: 1px solid #166534; border-radius: 10px;
    padding: 14px 18px; color: #ffffff; font-size: 0.9rem; margin-bottom: 12px;
}
.box-error {
    background: #1a0808; border: 1px solid #991b1b; border-radius: 10px;
    padding: 14px 18px; color: #ffffff; font-size: 0.9rem; margin-bottom: 12px;
}
.box-warning {
    background: #1a1200; border: 1px solid #92400e; border-radius: 10px;
    padding: 12px 16px; color: #ffffff; font-size: 0.84rem; margin-bottom: 8px;
}
.box-info {
    background: #0c1a30; border: 1px solid #1d4ed8; border-radius: 10px;
    padding: 12px 16px; color: #ffffff; font-size: 0.84rem; margin-bottom: 8px;
}

.stats-row { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-card {
    flex: 1; background: #161b27; border: 1px solid #2a3650;
    border-radius: 10px; padding: 14px 10px; text-align: center;
}
.stat-num   { color: #60a5fa; font-size: 1.7rem; font-weight: 700; line-height: 1.1; }
.stat-label { color: #ffffff; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; margin-top: 2px; }

.tip-box {
    background: #0c1220; border-left: 3px solid #2563eb;
    border-radius: 0 8px 8px 0; padding: 10px 14px;
    color: #ffffff; font-size: 0.82rem; margin-top: 10px;
}
.footer { text-align: center; color: #4a5a70; font-size: 0.75rem; border-top: 1px solid #161b27; padding-top: 14px; margin-top: 32px; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📊 DSA Question Dataset Generator</h1>
    <p>Paste raw DSA problem descriptions · Select mode · Download platform-ready <strong>.xlsx</strong></p>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "solution_mode" not in st.session_state:
    st.session_state["solution_mode"] = "non_function"
if "api_key" not in st.session_state:
    st.session_state["api_key"] = os.getenv("OPENROUTER_API_KEY", "")
# ── API Key input ─────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">🔑 OpenRouter API Key</div>', unsafe_allow_html=True)
api_key_input = st.text_input(
    label="api_key",
    label_visibility="collapsed",
    placeholder="sk-or-v1-...",
    type="password",
    value=st.session_state["api_key"],
    key="api_key_field",
)
if api_key_input:
    st.session_state["api_key"] = api_key_input

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── Mode toggle ───────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">⚙️ Solution Mode</div>', unsafe_allow_html=True)
is_func = st.session_state["solution_mode"] == "function"

mcol1, mcol2 = st.columns(2)
with mcol1:
    if st.button(
        "📄 Non-Function Based" + (" ✓" if not is_func else ""),
        key="btn_nonfunc",
        type="primary" if not is_func else "secondary",
        use_container_width=True,
    ):
        st.session_state["solution_mode"] = "non_function"
        st.rerun()
with mcol2:
    if st.button(
        "🔧 Function Based" + (" ✓" if is_func else ""),
        key="btn_func",
        type="primary" if is_func else "secondary",
        use_container_width=True,
    ):
        st.session_state["solution_mode"] = "function"
        st.rerun()

is_func = st.session_state["solution_mode"] == "function"
if is_func:
    st.markdown("""
    <div class="mode-active-pill pill-func">
        🔧 <strong>Function Based</strong> — Solutions use a <code>solution</code> class
        with a named method. Backend Code is filled. Output Format uses <em>"Return ..."</em>.
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="mode-active-pill pill-nonfunc">
        📄 <strong>Non-Function Based</strong> — Solutions use direct inline style inside
        <code>main()</code>. Backend Code is empty. Output Format uses <em>"Print ..."</em>.
    </div>""", unsafe_allow_html=True)

# ── Sub_Topics input ──────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">🏷️ Sub Topics (optional)</div>', unsafe_allow_html=True)

st.markdown("""
<div class="subtopic-box">
    <p style="color:#ffffff; font-size:0.88rem; margin:0 0 10px 0;">
        Use the format <code style="color:#60a5fa;">N - subtopic</code> — one per line, where <code style="color:#60a5fa;">N</code> is the question number.
        Each subtopic tells the generator <strong>which approach to use</strong> for that problem's solution.
        There are many ways to solve a problem — specifying a subtopic forces that technique.
    </p>
    <pre style="background:#0d1117; border:1px solid #2a3650; border-radius:8px; padding:12px 16px; color:#93c5fd; font-size:0.85rem; margin:0 0 12px 0; line-height:1.7;">1 - backtracking
2 - two_pointers
3 - sliding_window</pre>
    <p style="color:#94a3b8; font-size:0.8rem; margin:0 0 4px 0;">
        <strong style="color:#e2e8f0;">Approach-driven</strong> — solution is generated using that specific technique:
        <span style="color:#60a5fa;">backtracking &nbsp;·&nbsp; two_pointers &nbsp;·&nbsp; sliding_window &nbsp;·&nbsp; bit_manipulation &nbsp;·&nbsp; recursion &nbsp;·&nbsp; dynamic_programming</span>
    </p>
    <p style="color:#94a3b8; font-size:0.8rem; margin:8px 0 0 0;">
        <strong style="color:#e2e8f0;">Generic</strong> — simplest optimal solution, subtopic only fills the column:
        <span style="color:#60a5fa;">arrays &nbsp;·&nbsp; strings &nbsp;·&nbsp; math &nbsp;·&nbsp; sorting</span>
    </p>
    <p style="color:#4a5a70; font-size:0.76rem; margin:10px 0 0 0;">
        Leave blank to skip. If fewer subtopics than problems are given, remaining problems use the simplest solution.
    </p>
</div>
""", unsafe_allow_html=True)

subtopic_input = st.text_area(
    label="subtopics",
    label_visibility="collapsed",
    placeholder="1 - backtracking\n2 - two_pointers\n3 - sliding_window",
    height=110,
    key="subtopic_textarea",
)

# ── Problem input ─────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">📝 Problem Input</div>', unsafe_allow_html=True)

problem_input = st.text_area(
    label="problem_input",
    label_visibility="collapsed",
    placeholder=(
        "Paste 1–5 DSA problem descriptions here.\n\n"
        "Include for each problem:\n"
        "  • Problem statement / real-world context\n"
        "  • Input / Output format\n"
        "  • Constraints\n"
        "  • Example with explanation\n\n"
        "Separate multiple problems clearly with a blank line or heading."
    ),
    height=380,
    key="problem_textarea",
)

st.markdown("""
<div class="tip-box">
    💡 <strong>Tip:</strong> For best accuracy submit 1–5 problems per generation.
    Testcases are auto-verified by running the Python solution — outputs are corrected automatically.
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
generate_btn = st.button("🚀  Generate Dataset", key="generate_btn", use_container_width=True)

# ── Generation logic ──────────────────────────────────────────────────────────
if generate_btn:
    if not st.session_state.get("api_key", "").strip():
        st.markdown(
            '<div class="box-error">🔑 Please enter your OpenRouter API key above before generating.</div>',
            unsafe_allow_html=True,
        )
    elif not problem_input.strip():
        st.markdown(
            '<div class="box-error">⚠️ Please paste at least one DSA problem before generating.</div>',
            unsafe_allow_html=True,
        )
    else:
        is_func    = st.session_state["solution_mode"] == "function"
        mode_label = "FUNCTION BASED" if is_func else "NON-FUNCTION BASED"

        # Parse subtopics
        subtopics = parse_subtopics(subtopic_input) if subtopic_input.strip() else []

        with st.spinner(f"🤖 Claude is generating ({mode_label}) — please wait..."):
            try:
                # ── Step 1: Generate rows via Claude ─────────────────────────
                rows = generate_rows(
                    problem_input.strip(),
                    function_based=is_func,
                    subtopics=subtopics,
                    api_key=st.session_state["api_key"],
                )

                # ── Step 2: Validate structure ────────────────────────────────
                is_valid, messages = validate_rows(rows, function_based=is_func)
                for msg in messages:
                    st.markdown(
                        f'<div class="box-{"error" if not is_valid else "warning"}">'
                        f'{"❌" if not is_valid else "⚠️"} {msg}</div>',
                        unsafe_allow_html=True,
                    )
                if not is_valid:
                    st.stop()

                # ── Step 3: Run executor — auto-correct testcase outputs ──────
                rows, corrections = verify_and_fix_testcases(rows)
                if corrections > 0:
                    st.markdown(
                        f'<div class="box-info">🔧 Auto-corrected <strong>{corrections}</strong> '
                        f'testcase output(s) by running the Python solution.</div>',
                        unsafe_allow_html=True,
                    )

                # ── Step 3b: Replace last 3 TCs with generated large cases ────
                rows, injected, skipped_blocks = inject_stress_testcases(rows)
                if injected:
                    st.markdown(
                        f'<div class="box-info">📈 Generated <strong>{injected}</strong> '
                        f'large testcase(s) in code (no LLM).</div>',
                        unsafe_allow_html=True,
                    )
                if skipped_blocks:
                    st.markdown(
                        f'<div class="box-warning">⚠️ {skipped_blocks} question(s) had an '
                        f'unsupported input shape — large testcases skipped, '
                        f'Claude\'s originals kept.</div>',
                        unsafe_allow_html=True,
                    )

                # ── Step 4: Inject subtopics into PYTHON rows ─────────────────
                if subtopics:
                    rows = inject_subtopics(rows, subtopics)

                # ── Step 5: Generate xlsx ─────────────────────────────────────
                xlsx_bytes = rows_to_xlsx(rows)

                # ── Step 6: Stats ─────────────────────────────────────────────
                non_blank     = [r for r in rows if isinstance(r, dict) and any(r.get(k) for k in r)]
                python_rows   = [r for r in non_blank if r.get("Code_language") == "PYTHON"]
                num_questions = len(python_rows)
                total_rows    = len(rows)
                style_label   = "Function" if is_func else "Inline"

                st.markdown(f"""
                <div class="stats-row">
                    <div class="stat-card">
                        <div class="stat-num">{num_questions}</div>
                        <div class="stat-label">Question(s)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-num">{num_questions * 10}</div>
                        <div class="stat-label">Test Cases</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-num">{corrections}</div>
                        <div class="stat-label">TC Corrected</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-num" style="font-size:1rem; padding-top:4px;">{style_label}</div>
                        <div class="stat-label">Sol. Style</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(
                    '<div class="box-success">✅ <strong>Dataset generated successfully!</strong> '
                    'Click below to download your .xlsx file.</div>',
                    unsafe_allow_html=True,
                )

                st.download_button(
                    label="⬇️  Download Dataset (.xlsx)",
                    data=xlsx_bytes,
                    file_name="dsa_question_dataset.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            except anthropic.AuthenticationError:
                st.markdown(
                    '<div class="box-error">🔑 <strong>Key rejected by OpenRouter.</strong><br>'
                    'Check that it starts with sk-or-v1- and is still active at '
                    'openrouter.ai/keys.</div>',
                    unsafe_allow_html=True,
                )
            except anthropic.NotFoundError:
                st.markdown(
                    '<div class="box-error">🔍 <strong>Model not found.</strong><br>'
                    'Verify the MODEL slug in src/claude_client.py against '
                    'openrouter.ai/models.</div>',
                    unsafe_allow_html=True,
                )
            except anthropic.APIStatusError as ae:
                if ae.status_code == 402:
                    st.markdown(
                        '<div class="box-error">💳 <strong>Out of credit.</strong><br>'
                        'Top up your balance at openrouter.ai/credits.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="box-error">❌ <strong>API error {ae.status_code}:</strong><br>'
                        f'<pre style="margin:8px 0 0 0; font-size:0.78rem; color:#fca5a5;">{str(ae)}</pre></div>',
                        unsafe_allow_html=True,
                    )
            except ValueError as ve:
                st.markdown(
                    f'<div class="box-error">❌ <strong>Error:</strong><br>'
                    f'<pre style="margin:8px 0 0 0; font-size:0.78rem; color:#fca5a5;">{str(ve)}</pre></div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(
                    f'<div class="box-error">❌ <strong>Unexpected error:</strong><br>'
                    f'<pre style="margin:8px 0 0 0; font-size:0.78rem; color:#fca5a5;">'
                    f'{traceback.format_exc()}</pre></div>',
                    unsafe_allow_html=True,
                )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    DSA Dataset Generator &nbsp;·&nbsp; Streamlit + OpenRouter &nbsp;·&nbsp; anthropic/claude-sonnet-4.5
</div>
""", unsafe_allow_html=True)