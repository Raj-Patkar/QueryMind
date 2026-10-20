# QueryMind

Conversational natural-language-to-SQL for PostgreSQL. You connect a database, ask questions in plain English, and follow-ups like *"what about their salaries?"* are understood in context. Every model in the pipeline was trained by the project author (NLP & Deep Learning course project). Evaluated on the **college_2** database.

```
question + earlier questions
        │
        ▼
 ┌───────────────────┐   sql_ready          ┌──────────────────┐
 │ Ambiguity         │ ───────────────────► │ Question rewriter │  (only if there is history)
 │ classifier        │                      │ T5 → standalone Q │
 │ TF-IDF + LogReg   │                      └─────────┬────────┘
 └──────┬────────────┘                                ▼
        │ clarification_needed /              ┌──────────────────┐
        │ unanswerable / low confidence       │ Schema retrieval  │  3–8 relevant tables,
        ▼                                     │ MiniLM embeddings │  fits T5's 512 tokens
   message to user                            └─────────┬────────┘
                                                        ▼
                                              ┌──────────────────┐
                                              │ Experiment 3 T5   │  top-4 beam candidates
                                              │ text → SQL        │
                                              └─────────┬────────┘
                                                        ▼
                         string-literal fix ("x" → 'x') + SQLGlot schema validation
                                                        ▼
                  read-only execution on PostgreSQL (+ fallback to next candidate if 0 rows)
```

## 1. Project structure

```text
QueryMind/
  app/
    main.py                 FastAPI app: /health, /database/test, /query (validates, then executes read-only)
    pipeline.py             classifier → rewriter → retrieval → T5 → validation
    prompting.py            exact training-format prompts/schema text (matches the notebooks)
    retrieval.py            schema retrieval (Experiment 2 retriever, token-budgeted)
    rewriter.py             follow-up → standalone question (own fine-tuned T5)
    sql_fixes.py            double-quote → single-quote literals; best-of-N candidate choice
    dynamic_validator.py    SQLGlot validation against the discovered PostgreSQL schema
    postgres_connector.py   schema discovery + read-only execution (row cap, timeout)
    schema.py, validator.py legacy college-only static validator (kept for its tests)
  frontend/                 React + Vite chat UI (port 5173, proxies /api → 8000)
  tests/                    unit tests (no model files needed)
  artifacts/                model files (NOT in git, see section 3)
  requirements.txt
  .env.example
```

## 2. Prerequisites

- Python 3.10/3.11, Node 18+, PostgreSQL
- About 3 GB of disk for the models. A GPU is optional (`MODEL_DEVICE=auto` uses it if present). On CPU, expect a few seconds per question.

## 3. Model artifacts (`artifacts/`)

Model weights are too large for git. Create `artifacts/` and put these inside:

| Path | What it is |
|---|---|
| `querymind_ambiguity_classifier.joblib` | classifier: `sql_ready` / `clarification_needed` / `unanswerable` |
| `QueryMind_Experiment3_T5_Conversational/` | text-to-SQL T5 (config, tokenizer files, `model.safetensors`) |
| `querymind_rewriter/` | follow-up rewriter T5 (config, tokenizer files, `model.safetensors`) |

The retriever (`all-MiniLM-L6-v2`) downloads automatically on first start.

If a model folder was saved by a newer `transformers` than you have installed and fails with `'list' object has no attribute 'keys'`, delete the `"extra_special_tokens"` entry from its `tokenizer_config.json`. (`rewriter.py` already works around this by loading `tokenizer.json` directly.)

Only the T5 SQL model and the classifier are required. If the rewriter or retriever cannot load, the app still runs and falls back to its earlier behaviour (check `/health`).

## 4. Install and run

```bash
# backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # edit paths if yours differ
uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

Check `http://127.0.0.1:8000/health`. You want `models_ready`, `retriever_ready` and `rewriter_ready` all `true`; otherwise the matching `*_error` field says why.

### Load the sample database (college_2)

```bash
createdb college_db
psql -d college_db -f college_db_postgres.sql
```

In the app, connect with `postgresql://USER:PASSWORD@localhost:5432/college_db`.

## 5. Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `CLASSIFIER_PATH` | `./artifacts/querymind_ambiguity_classifier.joblib` | classifier artifact |
| `T5_MODEL_DIR` | `./artifacts/QueryMind_Experiment3_T5_Conversational` | text-to-SQL model |
| `REWRITER_DIR` | `./artifacts/querymind_rewriter` | follow-up rewriter |
| `RETRIEVER_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | table retriever |
| `MODEL_DEVICE` | `auto` | `auto`, `cpu` or `cuda` |
| `MIN_TOP_PROBABILITY` | `0.65` | classifier confidence gate |
| `MIN_PROBABILITY_MARGIN` | `0.00` | classifier top-2 margin gate |
| `SQL_NBEST` | `4` | beam candidates tried per question |
| `EXEC_FALLBACK` | `1` | `0` disables falling back to the next candidate when a query returns no rows |

## 6. API

### `GET /health`
`api`, `models_ready`, `load_errors`, `retriever_ready/_error`, `rewriter_ready/_error`.

### `POST /database/test`
```json
{ "connection_string": "postgresql://USER:PASSWORD@HOST:5432/DB", "schemas": ["public"] }
```
Connects and returns the discovered tables and columns.

### `POST /query`
```json
{
  "question": "what about their salaries?",
  "connection_string": "postgresql://USER:PASSWORD@HOST:5432/DB",
  "conversation_history": "List instructors in Physics",
  "schemas": ["public"]
}
```
`conversation_history` is the earlier **user** questions joined with ` | ` (or `none`); the models were trained on user questions only. The frontend does this automatically. The API keeps no session state.

Main response fields:

| Field | Meaning |
|---|---|
| `status` | `executed`, `clarification_needed`, `unanswerable`, `manual_review`, `invalid_sql`, `service_unavailable` |
| `sql`, `sql_validation` | the SQL that was run (or blocked) and the validator's findings |
| `execution` | `columns`, `rows` (max 200), `row_count`, `truncated` |
| `rewritten_question` | the standalone question the follow-up was turned into (`null` if not rewritten) |
| `tables_used` | tables put into the T5 prompt by retrieval |
| `prompt_truncated` | `true` if the prompt exceeded 512 tokens (should be `false`) |
| `sql_candidate_rank` | which beam candidate was chosen (0 = top) |
| `fallback_used`, `original_sql` | set when the top query returned no rows and the next candidate was shown |
| `predicted_status`, `probabilities` | classifier output |

## 7. Tests

```bash
pip install pytest
pytest -q
```
Covers prompt formats (checked against the training notebooks' exact strings), retrieval, the rewriter's input format and fallbacks, the quote/literal fix, candidate selection and the legacy validator. No model files needed.

## 8. How the pieces were built and measured

All numbers are **execution match** (does the generated SQL return the same rows as the gold SQL) on a **hand-written set of 80 turns in 33 conversations on college_2**, run in SQLite with the notebook pipeline. Small test set, so treat differences of a few points as noise.

| Setup | Overall | Follow-ups |
|---|---|---|
| Original app (prompt mismatch, prompt cut at 512 tokens) | 27.5% | 6.4% |
| + schema retrieval (history no longer truncated) | 43.8% | 36.2% |
| + trained question rewriter | 43.8% | 38.3% |
| Ceiling with a perfect rewriter | 56.2% | 57.4% |

What each step fixed:
1. **Prompt format**: the app now builds the schema/history text exactly as in training.
2. **Retrieval**: the full college_2 schema is about 720 tokens, so T5 silently cut the history. Retrieval keeps only relevant tables.
3. **Rewriter**: small T5 trained on about 29k generated college_2 conversations whose SQL was execution-verified. It handles pronouns, "what about X?", and added filters. It does not yet handle relational follow-ups ("which departments do they work in?"), sort/top-N, or "that instructor" references; those fall through unchanged.
4. **Later app fixes (not part of the table above; not separately measured)**: Spider-style `"value"` strings are converted to `'value'` for PostgreSQL; the top-4 beam candidates are tried and the first valid one is used; if a valid query returns no rows, the next valid candidate is tried.

Notebooks used: `QueryMind_Step2_College2_MultiTurn_Eval`, `QueryMind_Step4a_Retrieval_Eval`, `QueryMind_Step3_Rewriter` (training and evaluation of the rewriter). The rewriter's training data generator is `gen_rewriter_data.py`.

## 9. Known limitations

- **SQL model ceiling**: even with perfect inputs the T5 gets about 56–62% on the test set. It also cannot output the `<` character (not in its vocabulary), so "less than" questions may be wrong. Retraining with a placeholder token and more college data is the main next improvement.
- **Classifier**: weaker on college questions and does not read conversation history well; valid follow-ups can be routed to "clarification needed". Its 95% test accuracy is inflated by template-generated data.
- **Validation is static**: it checks tables and columns exist, not that the SQL answers the question. The empty-result fallback can show a different query's rows when a question truly has no answer; the UI says so when it happens.
- **Domain**: trained and tested on college_2 only. Other schemas are unevaluated.
- **Mixed-case Postgres identifiers** are not specially quoted for columns (college_db is all lowercase, so it works).

## 10. Security

This is a development build. Before any shared or public deployment:
- Add authentication; the API currently accepts any connection string with each request. Never commit or log connection strings.
- Restrict outbound network access to approved database hosts (SSRF) and use TLS.
- Use a least-privilege, read-only PostgreSQL user. The app already limits itself to a single `SELECT`, a read-only transaction, a 5 s statement timeout and 200 rows, but the database role is the real protection.