from __future__ import annotations

import json
from pathlib import Path

from app.dataset import (
    build_qc_report,
    extract_mcq_options,
    flatten_dataset_records,
    sanitize_runtime_sample,
)


def _load_raw() -> list[dict]:
    path = Path("data/raw/Logic_Based_Educational_Queries.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_flatten_count_order_and_ids() -> None:
    records = _load_raw()
    flattened = flatten_dataset_records(records)

    assert len(records) == 411
    assert len(flattened) == 808
    assert flattened[0]["record_id"] == 0
    assert flattened[0]["question_id"] == 0
    assert flattened[0]["sample_id"] == "record_0000_question_0000"
    assert flattened[1]["record_id"] == 0
    assert flattened[1]["question_id"] == 1

    last = flattened[-1]
    assert last["record_id"] == 410
    assert last["sample_id"].startswith("record_0410_question_")


def test_record_132_choices_are_canonicalized_into_question() -> None:
    records = _load_raw()
    flattened = flatten_dataset_records(records)
    sample = next(x for x in flattened if x["record_id"] == 132 and x["question_id"] == 0)

    question = sample["question"]
    options = extract_mcq_options(question)
    assert [label for label, _ in options] == ["A", "B", "C", "D"]
    assert "choices" not in sample
    assert sample["answer"] == "A"


def test_runtime_sanitizer_excludes_reference_only_fields() -> None:
    sample = {
        "sample_id": "record_0001_question_0000",
        "record_id": 1,
        "question_id": 0,
        "premises-NL": ["p1"],
        "question": "Q?",
        "premises-FOL": ["f1"],
        "answer": "Yes",
        "explanation": "because",
        "idx": [1],
        "choices": ["A. ..."],
    }
    safe = sanitize_runtime_sample(sample)
    assert set(safe.keys()) == {"sample_id", "record_id", "question_id", "premises-NL", "question"}


def test_qc_tags_include_premise_mismatch_and_conflict_signal() -> None:
    records = _load_raw()
    flattened = flatten_dataset_records(records)

    mismatch = [x for x in flattened if x["record_id"] in {34, 57, 146, 334, 376, 377, 378, 379, 380, 381, 382}]
    assert mismatch
    assert all("premise_count_mismatch" in x["qc_tags"] for x in mismatch)

    sample_37_1 = next(x for x in flattened if x["record_id"] == 37 and x["question_id"] == 1)
    assert "answer_explanation_conflict_signal" in sample_37_1["qc_tags"]


def test_mcq_extractability_diagnostics() -> None:
    samples = [
        {
            "sample_id": "record_0000_question_0000",
            "record_id": 0,
            "question_id": 0,
            "premises-NL": ["p"],
            "question": "What?\nA. a\nB. b\nC. c\nD. d",
            "answer": "A",
            "qc_tags": [],
        },
        {
            "sample_id": "record_0001_question_0000",
            "record_id": 1,
            "question_id": 0,
            "premises-NL": ["p"],
            "question": "What?",
            "answer": "B",
            "qc_tags": ["mcq_options_missing"],
        },
    ]
    report = build_qc_report(samples)
    assert report["mcq_extractability"]["missing_count"] == 1
    assert report["counts"]["mcq_options_missing"] == 1
