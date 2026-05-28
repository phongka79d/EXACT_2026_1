from __future__ import annotations

from app.candidate_extraction import (
    QUESTION_FAMILY_MCQ,
    QUESTION_FAMILY_OPEN_ENDED,
    QUESTION_FAMILY_YES_NO_UNKNOWN,
    classify_question_family,
    extract_question_candidates,
)


def _sample(question: str) -> dict:
    return {
        "sample_id": "record_0001_question_0000",
        "record_id": 1,
        "question_id": 0,
        "premises-NL": ["p1"],
        "question": question,
    }


def test_mcq_inline_extraction_and_order() -> None:
    question = "Which is correct?\nA. Alpha\nB. Beta\nC. Gamma\nD. Delta"
    result = extract_question_candidates(_sample(question))
    assert result["question_family"] == QUESTION_FAMILY_MCQ
    assert [c["label"] for c in result["candidates"]] == ["A", "B", "C", "D"]
    assert [c["text"] for c in result["candidates"]] == ["Alpha", "Beta", "Gamma", "Delta"]


def test_mcq_multiline_and_symbolic_preservation() -> None:
    question = (
        "Pick valid formula\n"
        "A. forall x (P(x) -> Q(x))\n"
        "B. exists y\n"
        "   (R(y) & S(y))\n"
        "C. (A -> B) & (~C v D)\n"
        "D. x + y >= 7"
    )
    result = extract_question_candidates(_sample(question))
    assert result["question_family"] == QUESTION_FAMILY_MCQ
    assert result["candidates"][0]["text"] == "forall x (P(x) -> Q(x))"
    assert result["candidates"][1]["text"] == "exists y\n   (R(y) & S(y))"
    assert result["candidates"][2]["text"] == "(A -> B) & (~C v D)"
    assert result["candidates"][3]["text"] == "x + y >= 7"


def test_yes_no_claim_extraction() -> None:
    result = extract_question_candidates(_sample("Is it true that Mai can graduate on time?"))
    assert result["question_family"] == QUESTION_FAMILY_YES_NO_UNKNOWN
    assert result["candidates"][0]["label"] == "claim"
    assert result["candidates"][0]["text"] == "Mai can graduate on time"
    assert result["candidates"][0]["supports_explicit_negation_check"] is True


def test_unknown_style_question_is_yes_no_unknown_family() -> None:
    result = extract_question_candidates(
        _sample("Is there enough information to conclude that John passed the exam?")
    )
    assert result["question_family"] == QUESTION_FAMILY_YES_NO_UNKNOWN
    assert "insufficient_evidence_style_question" in result["warnings"]
    assert result["candidates"][0]["text"] == "John passed the exam"


def test_open_ended_classification_and_policy_envelope() -> None:
    result = extract_question_candidates(_sample("What can we infer about Mai's eligibility?"))
    assert result["question_family"] == QUESTION_FAMILY_OPEN_ENDED
    assert result["candidates"][0]["label"] == "open_claim"
    assert result["candidates"][0]["policy"] == "synthesize_from_proof_trace_or_return_unknown"
    assert "open_ended_best_effort" in result["warnings"]


def test_candidate_extraction_error_summary() -> None:
    result = extract_question_candidates({"question": "Is this valid?"})
    assert result["question_family"] is None
    assert result["candidates"] == []
    assert result["errors"]
    assert result["debug_summary"]["extraction_errors"]
    assert result["debug_summary"]["candidate_count"] == 0


def test_classify_question_family_defaults() -> None:
    assert classify_question_family("Can Mai enroll next term?") == QUESTION_FAMILY_YES_NO_UNKNOWN
    assert classify_question_family("Explain why the rule applies.") == QUESTION_FAMILY_OPEN_ENDED
