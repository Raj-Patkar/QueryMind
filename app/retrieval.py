"""Schema retrieval for the T5 prompt (Step 4a).

Picks the 3-8 tables most similar to the question (plus earlier questions in the
conversation) so the prompt stays under T5's 512-token limit and conversation
history is no longer truncated away. Uses the Experiment 2 embedding model.
"""
from __future__ import annotations

import os

from app.prompting import build_t5_prompt, build_t5_schema_text, build_table_description

INITIAL_K = 3
MAX_TABLES = 8
SIM_THRESHOLD = 0.30
TOKEN_BUDGET = 508


class SchemaRetriever:
    def __init__(self):
        self.model = None
        self._cache: dict[tuple, object] = {}
        self.error = None

    def load(self):
        try:
            from sentence_transformers import SentenceTransformer

            name = os.getenv("RETRIEVER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            self.model = SentenceTransformer(name, device="cpu")
        except Exception as exc:  # retrieval is optional; fall back to the full schema
            self.model = None
            self.error = str(exc)

    @property
    def ready(self):
        return self.model is not None

    def _embed(self, texts):
        return self.model.encode(texts, normalize_embeddings=True)

    def _table_embeddings(self, schema_metadata):
        descs = [build_table_description(schema_metadata, t) for t in schema_metadata["tables"]]
        key = tuple(descs)
        if key not in self._cache:
            if len(self._cache) > 16:
                self._cache.clear()
            self._cache[key] = self._embed(descs)
        return self._cache[key]

    def select_tables(self, schema_metadata, question, history_questions, token_len):
        """Return table names to include. `token_len(prompt)` counts tokenizer tokens."""
        names = [t["table"] for t in schema_metadata["tables"]]
        if not self.ready or len(names) <= INITIAL_K:
            return names
        query_text = " ".join([*history_questions, question]).strip()
        sims = self._table_embeddings(schema_metadata) @ self._embed(query_text)
        order = sorted(range(len(names)), key=lambda i: -float(sims[i]))
        history_text = " | ".join(history_questions) if history_questions else "none"

        chosen: list[int] = []
        for rank, idx in enumerate(order):
            if rank >= MAX_TABLES:
                break
            if rank >= INITIAL_K:
                if float(sims[idx]) < SIM_THRESHOLD:
                    break
                trial = build_t5_prompt(
                    question,
                    build_t5_schema_text(schema_metadata, [names[i] for i in [*chosen, idx]]),
                    history_text,
                )
                if token_len(trial) > TOKEN_BUDGET:
                    break
            chosen.append(idx)
        keep = {names[i] for i in chosen}
        return [n for n in names if n in keep]  # original table order, as in training
