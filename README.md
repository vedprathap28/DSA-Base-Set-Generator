# 📊 DSA Question Dataset Generator — v4

Streamlit web app that converts raw DSA problem descriptions into
platform-ready `.xlsx` datasets using Claude AI.

---

## Quick Start

```bash
# 1. Extract ZIP, open folder in VS Code

# 2. Add API key to .env
ANTHROPIC_API_KEY=sk-ant-...

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python -m streamlit run app.py
```

App opens at `http://localhost:8501`

---

## How It Works

1. Select **Non-Function Based** or **Function Based** mode
2. Paste one or more DSA problem descriptions
3. Click **Generate Dataset**
4. Wait ~30–90 seconds
5. Download the `.xlsx` file

---

## Pipeline

```
raw problem text
      │
      ▼
generate_rows()          Claude writes the question, PY/JAVA/CPP solutions,
                          boilerplate, and TC1-TC7
      │
      ▼
validate_rows()          structural checks — blocks generation on critical errors
      │
      ▼
verify_and_fix_testcases()   runs each Python solution against TC1-TC7,
                              silently corrects any wrong expected output
      │
      ▼
inject_stress_testcases()    pure code, no LLM — overwrites TC8-TC10 with
                              large generated inputs, using the same solution
                              to compute their expected output
      │
      ▼
inject_subtopics()        (optional) maps your pasted subtopic list onto
                          the right PYTHON rows
      │
      ▼
rows_to_xlsx()            writes the final `.xlsx`
```

---

## Output Format (per question)

| Row | Language | Contents |
|-----|----------|----------|
| 1 | PYTHON | Question markdown + Python solution + boilerplate |
| 2 | JAVA | Java solution + boilerplate + **TC1** |
| 3 | CPP | C++ solution + boilerplate + **TC2** |
| 4–11 | — | **TC3–TC10** overflow rows |
| 12 | — | Blank separator |

- 14 exact columns · 10 testcases · PYTHON → JAVA → CPP order
- Sheet tab: `BASE_QUE_SET` · Arial 10 · wrap text · frozen header
- No NODEJS rows · S.No / Difficulty / Sub_Topics always empty

---

## Mode Differences

| | Non-Function Based | Function Based |
|---|---|---|
| Solution style | Direct inline in `main()` | `solution` class + named method |
| Backend Code | Empty | Filled (all 3 rows) |
| Output Format wording | "Print ..." | "Return ..." |
| Prefilled boilerplate | Simple `main()` stub | Class + function signature |

---

## Project Structure

```
dsa_dataset_generator/
├── app.py                  ← Streamlit UI (entry point)
├── requirements.txt
├── .env                    ← Add ANTHROPIC_API_KEY here
├── README.md
└── src/
    ├── __init__.py
    ├── system_prompt.py    ← Master prompt + mode injection
    ├── claude_client.py    ← API call + JSON extraction
    ├── subtopic_parser.py  ← Maps free-text subtopics to problem rows
    ├── executor.py         ← Runs solutions; auto-corrects wrong TC outputs
    ├── stress_gen.py       ← Generates TC8-TC10 (large stress testcases)
    ├── xlsx_generator.py   ← openpyxl writer
    └── validator.py        ← Structural validation
```