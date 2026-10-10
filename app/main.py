from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, SecretStr

from app.pipeline import QueryMindPipeline
from app.postgres_connector import (
    create_postgres_engine,
    discover_schema,
    DatabaseConnectionError,
)

load_dotenv()
pipeline = QueryMindPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline.load()
    yield


app = FastAPI(
    title="QueryMind API",
    version="0.2.0",
    description=(
        "Conversational natural-language-to-SQL API. Connects to a user-supplied "
        "PostgreSQL database, discovers its schema, and validates generated SQL. "
        "SQL execution is disabled in this version."
    ),
)
app.router.lifespan_context = lifespan


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    connection_string: SecretStr
    conversation_history: str = Field(default="none", max_length=8000)
    schemas: list[str] = Field(default_factory=lambda: ["public"], max_length=10)


class SchemaRequest(BaseModel):
    connection_string: SecretStr
    schemas: list[str] = Field(default_factory=lambda: ["public"], max_length=10)


@app.get("/health")
def health():
    return {
        "api": "ok",
        "models_ready": pipeline.ready,
        "load_errors": pipeline.load_errors,
        "database_execution_enabled": False,
    }


@app.post("/database/test")
def test_database(request: SchemaRequest):
    """Test a PostgreSQL connection and return discovered schema metadata."""
    engine = None
    try:
        engine = create_postgres_engine(request.connection_string.get_secret_value())
        schema = discover_schema(engine, request.schemas)
        return {
            "status": "connected",
            "table_count": schema["table_count"],
            "tables": schema["tables"],
            "schema_text": schema["schema_text"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if engine is not None:
            engine.dispose()


@app.post("/query")
def query(request: QueryRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")

    engine = None
    try:
        engine = create_postgres_engine(request.connection_string.get_secret_value())
        schema = discover_schema(engine, request.schemas)
        return pipeline.query(
            question=question,
            database="postgresql",
            conversation_history=request.conversation_history.strip() or "none",
            schema_text=schema["schema_text"],
            schema_metadata=schema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if engine is not None:
            engine.dispose()
