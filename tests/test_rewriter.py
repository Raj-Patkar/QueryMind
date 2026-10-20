from app.rewriter import QuestionRewriter, build_rewriter_input


def test_input_format_matches_training():
    assert build_rewriter_input("What about their salaries?", ["List instructors in Physics"]) == (
        "rewrite as standalone question: What about their salaries? history: List instructors in Physics"
    )
    assert build_rewriter_input("How many?", []) == "rewrite as standalone question: How many? history: none"


def test_history_capped_at_three():
    out = build_rewriter_input("q", ["a", "b", "c", "d", "e"])
    assert out.endswith("history: c | d | e")


def _rw(output):
    r = QuestionRewriter()
    r.model = r.tokenizer = object()   # mark ready
    r._generate = lambda text: output
    return r


def test_not_ready_or_no_history_returns_original():
    assert QuestionRewriter().rewrite("q", ["h"]) == ("q", False)
    assert _rw("anything").rewrite("List all students.", []) == ("List all students.", False)


def test_cannot_rewrite_and_empty_fall_back():
    assert _rw("CANNOT_REWRITE").rewrite("how many", ["h"]) == ("how many", False)
    assert _rw("").rewrite("how many", ["h"]) == ("how many", False)


def test_rewrite_is_used():
    assert _rw("How many students are in Math?").rewrite("and math?", ["h"]) == ("How many students are in Math?", True)
    assert _rw("same question").rewrite("Same Question", ["h"])[1] is False
