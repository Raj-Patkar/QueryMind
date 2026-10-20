"""Question rewriter (Step 3): turns (earlier questions + follow-up) into a standalone question.

Uses the user's own fine-tuned T5 (querymind_rewriter). It is only applied when there is
conversation history; first questions are already standalone and are left untouched.
If the model is missing or answers CANNOT_REWRITE, the original question is used.
"""
from __future__ import annotations

import os
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MAX_IN, MAX_OUT, MAX_HISTORY = 192, 64, 3   # same limits as the training notebook


def build_rewriter_input(question: str, history_questions: list[str]) -> str:
    # Must match the training format exactly (gen_rewriter_data.input_format).
    hist = " | ".join(history_questions[-MAX_HISTORY:]) if history_questions else "none"
    return f"rewrite as standalone question: {question.strip()} history: {hist}"


def _load_tokenizer(path: str):
    """Load the tokenizer; fall back to the raw tokenizer files.

    A tokenizer saved by a newer `transformers` (e.g. in Colab) can fail to load in an older
    local install with "'list' object has no attribute 'keys'" (a tokenizer_config.json
    format change: the "extra_special_tokens" entry). The tokenizer itself lives in
    tokenizer.json (or spiece.model), so build it directly from that file and ignore the config.
    """
    try:
        return AutoTokenizer.from_pretrained(path, local_files_only=True)
    except Exception:
        tok_json, spiece = Path(path) / "tokenizer.json", Path(path) / "spiece.model"
        if tok_json.exists():
            from transformers import PreTrainedTokenizerFast
            return PreTrainedTokenizerFast(
                tokenizer_file=str(tok_json), eos_token="</s>", unk_token="<unk>", pad_token="<pad>"
            )
        if spiece.exists():
            from transformers import T5Tokenizer
            return T5Tokenizer(str(spiece))
        raise


class QuestionRewriter:
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.device = "cpu"
        self.error = None

    def load(self, device: str = "cpu"):
        path = os.getenv("REWRITER_DIR", "./artifacts/querymind_rewriter")
        try:
            if not Path(path).exists():
                raise FileNotFoundError(f"Rewriter directory not found: {path}")
            self.tokenizer = _load_tokenizer(path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(path, local_files_only=True)
            self.model.to(device).eval()
            self.device = device
        except Exception as exc:  # optional component: the app still works without it
            self.tokenizer = self.model = None
            self.error = str(exc)

    @property
    def ready(self):
        return self.model is not None and self.tokenizer is not None

    def _generate(self, text: str) -> str:
        enc = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_IN).to(self.device)
        with torch.no_grad():
            out = self.model.generate(**enc, max_new_tokens=MAX_OUT, num_beams=4, early_stopping=True, use_cache=True)
        return self.tokenizer.decode(out[0], skip_special_tokens=True).strip()

    def rewrite(self, question: str, history_questions: list[str]) -> tuple[str, bool]:
        """-> (question to use, whether it was rewritten)."""
        if not self.ready or not history_questions:
            return question, False
        try:
            out = self._generate(build_rewriter_input(question, history_questions))
        except Exception:
            return question, False
        if not out or out == "CANNOT_REWRITE":
            return question, False
        return out, out.strip().lower() != question.strip().lower()