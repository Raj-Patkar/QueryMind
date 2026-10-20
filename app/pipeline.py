import os
from pathlib import Path

import joblib
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from app.dynamic_validator import validate_sql_against_schema
from app.prompting import (
    build_classifier_schema_text,
    build_t5_prompt,
    build_t5_schema_text,
    history_for_classifier,
    history_for_t5,
    normalize_history,
)


class QueryMindPipeline:
    def __init__(self):
        self.classifier = None
        self.tokenizer = None
        self.t5_model = None
        self.device = "cpu"
        self.load_errors = []
        self.last_prompt_truncated = False

    def load(self):
        self.load_errors = []
        classifier_path = os.getenv(
            "CLASSIFIER_PATH",
            "./artifacts/querymind_ambiguity_classifier.joblib",
        )
        model_dir = os.getenv(
            "T5_MODEL_DIR",
            "./artifacts/QueryMind_Experiment3_T5_Conversational",
        )

        try:
            if not Path(classifier_path).exists():
                raise FileNotFoundError(f"Classifier artifact not found: {classifier_path}")
            self.classifier = joblib.load(classifier_path)
        except Exception as exc:
            self.classifier = None
            self.load_errors.append(f"classifier: {exc}")

        try:
            if not Path(model_dir).exists():
                raise FileNotFoundError(f"T5 model directory not found: {model_dir}")
            requested_device = os.getenv("MODEL_DEVICE", "auto").lower()
            self.device = (
                "cuda"
                if requested_device == "auto" and torch.cuda.is_available()
                else "cpu" if requested_device == "auto" else requested_device
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_dir, local_files_only=True
            )
            self.t5_model = AutoModelForSeq2SeqLM.from_pretrained(
                model_dir, local_files_only=True
            )
            self.t5_model.to(self.device)
            self.t5_model.eval()
        except Exception as exc:
            self.tokenizer = None
            self.t5_model = None
            self.load_errors.append(f"t5: {exc}")

    @property
    def ready(self):
        return (
            self.classifier is not None
            and self.tokenizer is not None
            and self.t5_model is not None
        )

    def _classify(self, question, schema, database, history):
        # Keep this input prefix aligned with the classifier's training format.
        parts = [
            "classify database question:",
            f"Database: {database}.",
            f"Schema: {schema}.",
        ]
        if history and history.strip().lower() != "none":
            parts.append(f"Conversation history: {history}.")
        parts.append(f"Question: {question}")
        model_input = " ".join(parts)

        predicted = str(self.classifier.predict([model_input])[0])
        probs = self.classifier.predict_proba([model_input])[0]
        classifier_step = self.classifier.named_steps.get("classifier")
        classes = (
            classifier_step.classes_
            if classifier_step is not None
            else self.classifier.classes_
        )
        ranked = sorted(
            [(str(label), float(prob)) for label, prob in zip(classes, probs)],
            key=lambda item: item[1],
            reverse=True,
        )
        top = ranked[0][1]
        margin = top - (ranked[1][1] if len(ranked) > 1 else 0.0)
        return {
            "status": predicted,
            "probabilities": {label: round(prob, 4) for label, prob in ranked},
            "top_probability": top,
            "margin": margin,
        }

    def _generate_sql(self, question, t5_schema, history_text):
        prompt = build_t5_prompt(question, t5_schema, history_text)
        # The model was trained with max_length=512; anything longer is cut from the
        # END of the prompt (i.e. the conversation history goes first). Report it.
        full_len = len(self.tokenizer(prompt, truncation=False)["input_ids"])
        self.last_prompt_truncated = full_len > 512
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self.device)
        with torch.no_grad():
            outputs = self.t5_model.generate(
                **inputs,
                max_new_tokens=128,
                num_beams=4,
                early_stopping=True,
            )
        return self.tokenizer.decode(
            outputs[0], skip_special_tokens=True
        ).strip()

    def query(
        self,
        question,
        database="postgresql",
        conversation_history="none",
        schema_text=None,
        schema_metadata=None,
    ):
        if not self.ready:
            return {
                "status": "service_unavailable",
                "action": "models_not_loaded",
                "message": "QueryMind models are not loaded. Check artifact paths and server logs.",
                "sql": None,
                "sql_validation": None,
            }

        if not schema_text or not schema_metadata:
            return {
                "status": "service_unavailable",
                "action": "schema_missing",
                "message": "A connected PostgreSQL schema is required for each query.",
                "sql": None,
                "sql_validation": None,
            }

        # Rebuild both prompts from the metadata so they match the TRAINING formats
        # (see app/prompting.py); the generic schema_text is only used for display.
        history_questions = normalize_history(conversation_history)
        classifier_schema = build_classifier_schema_text(schema_metadata)
        t5_schema = build_t5_schema_text(schema_metadata)

        route = self._classify(
            question,
            classifier_schema,
            database,
            history_for_classifier(history_questions),
        )
        min_prob = float(os.getenv("MIN_TOP_PROBABILITY", "0.65"))
        min_margin = float(os.getenv("MIN_PROBABILITY_MARGIN", "0.00"))
        base = {
            "question": question,
            "predicted_status": route["status"],
            "probabilities": route["probabilities"],
            "top_probability": round(route["top_probability"], 4),
            "probability_margin": round(route["margin"], 4),
        }

        if (
            route["top_probability"] < min_prob
            or route["margin"] < min_margin
        ):
            return {
                **base,
                "status": "manual_review",
                "action": "manual_review",
                "message": "Confidence is below the provisional routing threshold. Please review or clarify the request.",
                "sql": None,
                "sql_validation": None,
            }

        if route["status"] == "clarification_needed":
            return {
                **base,
                "status": "clarification_needed",
                "action": "ask_clarification",
                "message": "Could you clarify which item, person, time period, or relationship you mean?",
                "sql": None,
                "sql_validation": None,
            }

        if route["status"] == "unanswerable":
            return {
                **base,
                "status": "unanswerable",
                "action": "explain_unanswerable",
                "message": "The requested information does not appear to be available in the connected PostgreSQL schema.",
                "sql": None,
                "sql_validation": None,
            }

        if route["status"] != "sql_ready":
            return {
                **base,
                "status": "manual_review",
                "action": "unknown_classifier_label",
                "message": "Unknown classifier label; no SQL was generated.",
                "sql": None,
                "sql_validation": None,
            }

        sql = self._generate_sql(
            question, t5_schema, history_for_t5(history_questions)
        )
        base["prompt_truncated"] = self.last_prompt_truncated
        validation = validate_sql_against_schema(sql, schema_metadata)

        if validation["status"] == "invalid":
            return {
                **base,
                "status": "invalid_sql",
                "action": "sql_blocked_invalid",
                "message": "Generated SQL failed validation against the connected database schema. It was not executed.",
                "sql": sql,
                "sql_validation": validation,
            }

        if validation["status"] == "needs_review":
            return {
                **base,
                "status": "manual_review",
                "action": "manual_review_sql_structure",
                "message": "Generated SQL uses a structure this validator cannot fully check. It was not executed.",
                "sql": sql,
                "sql_validation": validation,
            }

        return {
            **base,
            "status": "sql_ready_for_review",
            "action": "sql_generated_validated_not_executed",
            "message": "SQL passed static checks against the connected schema. It has not been executed; semantic correctness is not guaranteed.",
            "sql": validation["normalized_sql"],
            "sql_validation": validation,
        }
