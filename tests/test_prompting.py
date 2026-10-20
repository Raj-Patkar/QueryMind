"""Checks the app's prompts against the exact strings produced by the training notebooks."""
from app.prompting import (
    build_classifier_schema_text,
    build_t5_prompt,
    build_t5_schema_text,
    history_for_t5,
    normalize_history,
    spider_type,
)

# Same toy schema as QueryMind_Experiment3_T5_Conversational_Colab_NoUpload.ipynb,
# expressed in the metadata shape postgres_connector.discover_schema returns.
META = {
    "tables": [
        {
            "table": "student",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "VARCHAR(50)", "primary_key": False},
                {"name": "course_id", "type": "VARCHAR(10)", "primary_key": False},
            ],
            "primary_key": ["id"],
            "foreign_keys": [
                {"columns": ["course_id"], "referred_table": "course", "referred_columns": ["course_id"]}
            ],
        },
        {
            "table": "course",
            "columns": [
                {"name": "course_id", "type": "VARCHAR(10)", "primary_key": True},
                {"name": "title", "type": "TEXT", "primary_key": False},
            ],
            "primary_key": ["course_id"],
            "foreign_keys": [],
        },
    ]
}

NOTEBOOK_OUTPUT = (
    "TABLE student: id(number) PRIMARY KEY, name(text), course_id(text) | "
    "TABLE course: course_id(text) PRIMARY KEY, title(text) | "
    "FOREIGN KEYS: student.course_id = course.course_id"
)


def test_t5_schema_matches_training_notebook():
    assert build_t5_schema_text(META) == NOTEBOOK_OUTPUT


def test_t5_prompt_matches_training_notebook():
    prompt = build_t5_prompt("List the names of all students.", NOTEBOOK_OUTPUT, "none")
    assert prompt == (
        "translate conversational English to SQL: "
        "Question: List the names of all students. "
        "Schema: " + NOTEBOOK_OUTPUT + " Conversation history: none"
    )


def test_classifier_schema_matches_dataset_style():
    assert build_classifier_schema_text(META) == "student(id, name, course_id); course(course_id, title)"


def test_history_drops_assistant_text_and_roles():
    legacy = (
        "user: List the names of all students.\n"
        "assistant: I ran your query successfully and found 12 rows.\n"
        "user: What about their courses?"
    )
    qs = normalize_history(legacy)
    assert qs == ["List the names of all students.", "What about their courses?"]
    assert history_for_t5(qs) == "List the names of all students. | What about their courses?"


def test_history_none_and_pipe_format():
    assert normalize_history("none") == []
    assert normalize_history(None) == []
    assert normalize_history("a? | b?") == ["a?", "b?"]
    assert history_for_t5([]) == "none"


def test_history_is_capped():
    many = " | ".join(f"q{i}" for i in range(20))
    assert normalize_history(many) == [f"q{i}" for i in range(14, 20)]


def test_spider_types():
    assert spider_type("INTEGER") == "number"
    assert spider_type("NUMERIC(10, 2)") == "number"
    assert spider_type("VARCHAR(255)") == "text"
    assert spider_type("TIMESTAMP WITHOUT TIME ZONE") == "time"
    assert spider_type("BOOLEAN") == "boolean"
    assert spider_type("JSONB") == "others"
