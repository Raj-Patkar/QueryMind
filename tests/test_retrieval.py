import numpy as np

from app.prompting import build_t5_schema_text, build_table_description
from app.retrieval import SchemaRetriever
from tests.test_prompting import META, NOTEBOOK_OUTPUT


def _table(name, cols, fks=()):
    return {
        "table": name,
        "columns": [{"name": c, "type": "TEXT", "primary_key": i == 0} for i, c in enumerate(cols)],
        "primary_key": [cols[0]],
        "foreign_keys": [
            {"columns": [a], "referred_table": t, "referred_columns": [b]} for a, t, b in fks
        ],
    }


BIG = {"tables": [_table(f"t{i}", [f"c{i}", "x"]) for i in range(10)]}


class FakeModel:
    """Bag-of-words 'embedding' over t0..t9 so similarity is predictable."""

    def encode(self, texts, normalize_embeddings=True):
        single = isinstance(texts, str)
        out = []
        for t in [texts] if single else texts:
            v = np.array([float(f"t{i}" in t.lower().replace(":", " ").split()) for i in range(10)])
            n = np.linalg.norm(v)
            out.append(v / n if n else v)
        return out[0] if single else np.array(out)


def _retriever():
    r = SchemaRetriever()
    r.model = FakeModel()
    return r


def test_full_subset_equals_full_schema():
    names = [t["table"] for t in META["tables"]]
    assert build_t5_schema_text(META, names) == build_t5_schema_text(META) == NOTEBOOK_OUTPUT


def test_subset_drops_foreign_keys_to_missing_tables():
    assert build_t5_schema_text(META, ["student"]) == (
        "TABLE student: id(number) PRIMARY KEY, name(text), course_id(text)"
    )


def test_table_description_includes_incoming_and_outgoing_fks():
    d = build_table_description(META, META["tables"][1])
    assert d.startswith("TABLE course: course_id (text) PRIMARY KEY, title (text)")
    assert "FOREIGN KEY: student.course_id = course.course_id" in d


def test_small_schema_skips_retrieval():
    assert _retriever().select_tables(META, "anything", [], lambda p: 10) == ["student", "course"]


def test_without_model_uses_all_tables():
    names = [t["table"] for t in BIG["tables"]]
    assert SchemaRetriever().select_tables(BIG, "q", [], lambda p: 10) == names


def test_history_pulls_in_tables_and_budget_limits():
    r = _retriever()
    # follow-up mentions nothing itself; history names t7 -> t7 must be selected
    got = r.select_tables(BIG, "how many of them?", ["list t7 rows"], lambda p: 10)
    assert "t7" in got and len(got) >= 3
    # a tiny token budget stops growth at the initial 3
    assert len(r.select_tables(BIG, "t1 t2 t3 t4 t5", [], lambda p: 9999)) == 3
    # original table order is preserved
    assert got == sorted(got, key=lambda n: int(n[1:]))
