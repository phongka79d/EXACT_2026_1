from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

RUNTIME_FIELDS = ("sample_id", "record_id", "question_id", "premises-NL", "question")
REFERENCE_FIELDS = ("premises-FOL", "answer", "explanation", "idx")
OPTION_LABELS = ("A", "B", "C", "D")

_OPTION_RE = re.compile(r"^\s*([A-D])\.\s+(.+?)\s*$", re.MULTILINE)


def load_raw_dataset(path: str | Path) -> List[Dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def canonicalize_question_with_choices(question: str, choices: Iterable[str]) -> str:
    base = question.rstrip()
    existing = {label for label, _ in extract_mcq_options(base)}
    lines = [base] if base else []
    for idx, choice in enumerate(choices):
        if idx >= len(OPTION_LABELS):
            break
        label = OPTION_LABELS[idx]
        if label in existing:
            continue
        lines.append(f"{label}. {str(choice).strip()}")
    return "\n".join(lines).strip()


def extract_mcq_options(question: str) -> List[Tuple[str, str]]:
    return [(label, text.strip()) for label, text in _OPTION_RE.findall(question or "")]


def has_answer_explanation_conflict_signal(answer: Any, explanation: Any) -> bool:
    if not isinstance(answer, str) or not isinstance(explanation, str):
        return False
    ans = answer.strip().lower()
    exp = explanation.strip().lower()
    if ans == "yes":
        return any(token in exp for token in ("cannot", "can't", "not true", "false", "no,"))
    if ans == "no":
        return any(token in exp for token in (" is true", "true.", "therefore true", "yes,"))
    return False


def _sample_id(record_id: int, question_id: int) -> str:
    return f"record_{record_id:04d}_question_{question_id:04d}"


def flatten_dataset_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    for record_id, record in enumerate(records):
        premises_nl = record.get("premises-NL", [])
        premises_fol = record.get("premises-FOL", [])
        questions = record.get("questions", [])
        answers = record.get("answers", [])
        explanations = record.get("explanation", [])
        idxs = record.get("idx", [])
        choices = record.get("choices")

        for question_id, raw_question in enumerate(questions):
            question = str(raw_question)
            if isinstance(choices, list) and choices:
                question = canonicalize_question_with_choices(question, choices)

            sample: Dict[str, Any] = {
                "sample_id": _sample_id(record_id, question_id),
                "record_id": record_id,
                "question_id": question_id,
                "premises-NL": premises_nl,
                "question": question,
                "premises-FOL": premises_fol,
                "answer": answers[question_id] if question_id < len(answers) else None,
                "explanation": explanations[question_id] if question_id < len(explanations) else None,
                "idx": idxs[question_id] if question_id < len(idxs) else None,
                "qc_tags": [],
            }

            if len(premises_nl) != len(premises_fol):
                sample["qc_tags"].append("premise_count_mismatch")
            if has_answer_explanation_conflict_signal(sample["answer"], sample["explanation"]):
                sample["qc_tags"].append("answer_explanation_conflict_signal")
            answer = str(sample.get("answer", "")).strip().upper()
            if answer in OPTION_LABELS and len(extract_mcq_options(question)) == 0:
                sample["qc_tags"].append("mcq_options_missing")

            flattened.append(sample)
    return flattened


def sanitize_runtime_sample(sample: Dict[str, Any], include_local_ids: bool = True) -> Dict[str, Any]:
    required = ("premises-NL", "question")
    for key in required:
        if key not in sample:
            raise ValueError(f"Missing required runtime field: {key}")
    if include_local_ids:
        for key in ("sample_id", "record_id", "question_id"):
            if key not in sample:
                raise ValueError(f"Missing required local id field: {key}")
        allow = set(RUNTIME_FIELDS)
    else:
        allow = {"premises-NL", "question"}
    return {key: sample[key] for key in allow}


def sanitize_runtime_samples(samples: List[Dict[str, Any]], include_local_ids: bool = True) -> List[Dict[str, Any]]:
    return [sanitize_runtime_sample(sample, include_local_ids=include_local_ids) for sample in samples]


def load_flattened_dataset(path: str | Path) -> List[Dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_qc_report(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    mcq_missing: List[Dict[str, Any]] = []
    for sample in samples:
        tags = sample.get("qc_tags", [])
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
            if tag == "mcq_options_missing":
                mcq_missing.append(
                    {
                        "sample_id": sample.get("sample_id"),
                        "record_id": sample.get("record_id"),
                        "question_id": sample.get("question_id"),
                    }
                )
    return {
        "total_samples": len(samples),
        "counts": counts,
        "mcq_extractability": {
            "missing_count": len(mcq_missing),
            "missing_samples": mcq_missing,
        },
    }
