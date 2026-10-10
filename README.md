# QueryMind API Starter

This is the first integrated API prototype, based on the current QueryMind notebook pipeline:
ambiguity classifier -> confidence gate -> Experiment 3 T5 -> SQLGlot/schema validation.

**Safety boundary:** this starter does not connect to PostgreSQL and never executes generated SQL. It only returns SQL that passed the current conservative static validator as `sql_ready_for_review`.

## 1. Project structure

```text
QueryMind_API_Starter/
  app/
    main.py
    pipeline.py
    schema.py
    validator.py
  tests/
    test_validator.py
  artifacts/                  # create this and copy model artifacts here
  requirements.txt
  .env.example
```

## 2. Put the model artifacts in place

Create `artifacts/` and copy:
- `querymind_ambiguity_classifier.joblib`
- `QueryMind_Experiment3_T5_Conversational/` (the extracted model directory containing config + model weights + tokenizer files)

If your T5 model is a ZIP, extract it so `config.json` and the model weights are inside the model directory. Do not copy only `config.json`/tokenizer files without the trained weights.

The classifier `.joblib` should be the artifact saved by the existing classifier notebook, not a newly trained model. Preserve its metadata JSON alongside it if available.

## 3. Install and configure

Python 3.10 or 3.11 is recommended for broad package compatibility. Create a virtual environment, activate it, then run:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` if the model paths differ. Environment variables are loaded by your shell/process manager; if using `.env` directly, run with a dotenv loader or export the values. This starter intentionally avoids automatic database configuration.

## 4. Run API

From this directory:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

Health can show `models_ready: false` if either artifact path is wrong. Review `load_errors`; no SQL will be generated until both models load.

## 5. Example request

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"List the names of all students.","database":"college_2","conversation_history":"none"}'
```

Expected response is one of:
- `clarification_needed`
- `unanswerable`
- `manual_review`
- `invalid_sql`
- `sql_ready_for_review`

The exact outcome depends on the loaded classifier and T5 artifacts. Do not expect every query to return SQL.

## 6. Run static validator tests without model artifacts

```bash
pytest -q
```

These tests cover only the validator and do not require model artifacts to be loaded. Install pytest first if needed:

```bash
pip install pytest
```

## 7. Important limitations

- The current validator auto-checks only a narrow single-table SELECT subset.
- Joins, CTEs, subqueries, and set operations are routed to manual review.
- Passing static validation does not prove SQL answers the question correctly.
- Confidence threshold `0.65` is provisional; College_2 routing recall was weak in the 30-question smoke test.
- Database execution is intentionally absent. Do not add it until the API regression suite is reviewed and the database uses a read-only role, statement timeout, row cap, and server-side read-only safeguards.
- Keep the schema metadata synchronized with the real database.


# QueryMind PostgreSQL connection integration

## Files to copy

Copy these files into the existing QueryMind project:

- Replace `app/main.py` with this package's `app/main.py`.
- Replace `app/pipeline.py` with this package's `app/pipeline.py`.
- Add `app/postgres_connector.py` from this package.
- Add `app/dynamic_validator.py` from this package.
- Add the three dependencies in `ADD_TO_requirements.txt` to your existing `requirements.txt`.

Do not delete or replace the model files under `artifacts/`.

## API changes

### `GET /health`
Returns API/model readiness and confirms execution remains disabled.

### `POST /database/test`
Connects to PostgreSQL and returns discovered schema metadata.

Request:
```json
{
  "connection_string": "postgresql://USER:PASSWORD@HOST:5432/DATABASE",
  "schemas": ["public"]
}
```

### `POST /query`
Discovers the supplied database schema for this request, passes the schema and history to the classifier/T5 pipeline, and validates candidate SQL against that discovered schema. SQL is not executed.

Request:
```json
{
  "question": "List the names of all students.",
  "connection_string": "postgresql://USER:PASSWORD@HOST:5432/DATABASE",
  "conversation_history": "none",
  "schemas": ["public"]
}
```

Use real credentials locally; never commit them to source control. A connection string is a secret. Do not send it to a frontend unless the application uses HTTPS, authenticated requests, and a backend architecture specifically designed to handle secrets. Do not log request bodies.

## Security and deployment notes

- This is a development integration. Do not expose arbitrary database connection strings to unauthenticated public users.
- Add authentication and authorization before deployment.
- Restrict outbound network access to approved database hosts to mitigate SSRF and internal-network access.
- Use TLS where supported and a least-privilege PostgreSQL user with read-only permissions.
- Current `/query` generates and validates SQL but does not execute it. The helper connector contains a separate read-only execution function, but it is deliberately not wired into the API yet.
- Only the configured schemas (default `public`) are introspected.
- The classifier/T5 artifacts and model metrics are unchanged. Dynamic schemas may differ significantly from training schemas, so quality must be evaluated on representative databases.
- SQLGlot-based validation is static and conservative; it does not guarantee semantic correctness.
- `conversation_history` remains a string. The client must send the previous turns in that string; this API does not persist sessions automatically.
- Use the existing model directories and environment settings `CLASSIFIER_PATH`, `T5_MODEL_DIR`, `MODEL_DEVICE`, `MIN_TOP_PROBABILITY`, and `MIN_PROBABILITY_MARGIN`.
