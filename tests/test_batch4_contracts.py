from __future__ import annotations

import pytest

from app.ast_contracts import ASTValidationError, validate_ast
from app.frame_artifacts import ArtifactContractError, build_frame_event, serialize_frame_events_jsonl
from app.frame_compiler import FrameCompileError, compile_frame_to_ast
from app.parse_frames import FrameValidationError, validate_parse_frame


def test_parse_frame_schema_valid_and_invalid() -> None:
    valid = {
        "kind": "rule",
        "if": [{"type": "numeric_condition", "entity": "student", "attribute": "gpa", "op": ">=", "value": 7.0}],
        "then": [{"type": "predicate", "entity": "student", "name": "allowed_change_major", "polarity": True}],
        "source_id": "premise_0001",
        "source_text": "Students with GPA >= 7.0 can change majors.",
        "premise_id": 1,
        "warnings": [],
    }
    assert validate_parse_frame(valid) == valid

    invalid = dict(valid)
    invalid.pop("premise_id")
    with pytest.raises(FrameValidationError):
        validate_parse_frame(invalid)


def test_ast_schema_valid_and_invalid() -> None:
    ast = {
        "metadata": {"source_id": "premise_1", "source_text": "x"},
        "node": {
            "type": "forall",
            "var": "student",
            "body": {
                "type": "implies",
                "if": {"type": "pred", "name": "eligible", "args": [{"type": "var", "name": "student"}]},
                "then": {"type": "pred", "name": "approved", "args": [{"type": "var", "name": "student"}]},
            },
        },
    }
    assert validate_ast(ast) == ast

    bad = {
        "metadata": {"source_id": "premise_1", "source_text": "x"},
        "node": {"type": "pred", "name": "approved", "args": [{"type": "var", "name": "student"}]},
    }
    with pytest.raises(ASTValidationError, match="unbound variable"):
        validate_ast(bad)


def test_compiler_converts_rule_fact_claim_and_compound() -> None:
    rule = {
        "kind": "rule",
        "if": [{"type": "predicate", "entity": "Mai", "name": "has_scholarship", "polarity": True}],
        "then": [{"type": "predicate", "entity": "Mai", "name": "tuition_waived", "polarity": False}],
        "source_id": "premise_2",
        "source_text": "If Mai has scholarship then tuition is not waived.",
        "premise_id": 2,
        "warnings": [],
    }
    fact = {
        "kind": "fact",
        "facts": [{"type": "numeric_value", "entity": "Mai", "attribute": "gpa", "value": 7.2}],
        "source_id": "premise_3",
        "source_text": "Mai has GPA 7.2.",
        "premise_id": 3,
        "warnings": [],
    }
    claim = {
        "kind": "claim",
        "claim": {"type": "predicate", "entity": "Mai", "name": "can_change_major", "polarity": True},
        "source_id": "question",
        "source_text": "Can Mai change major?",
        "candidate_label": "claim",
        "warnings": [],
    }
    compound = {
        "kind": "compound",
        "operator": "and",
        "operands": [
            {"type": "predicate", "entity": "Mai", "name": "eligible", "polarity": True},
            {"type": "predicate", "entity": "Mai", "name": "has_debt", "polarity": False},
        ],
        "source_id": "premise_4",
        "source_text": "Mai is eligible and does not have debt.",
        "premise_id": 4,
        "warnings": [],
    }

    rule_ast = compile_frame_to_ast(rule)
    fact_ast = compile_frame_to_ast(fact)
    claim_ast = compile_frame_to_ast(claim)
    compound_ast = compile_frame_to_ast(compound)

    assert rule_ast["node"]["type"] in {"forall", "implies"}
    assert fact_ast["node"]["type"] == "compare"
    assert claim_ast["metadata"]["candidate_label"] == "claim"
    assert compound_ast["node"]["type"] == "and"


def test_compiler_rejects_ambiguous_and_lossy() -> None:
    ambiguous = {
        "kind": "ambiguous",
        "reason": "insufficient parse confidence",
        "source_id": "premise_8",
        "source_text": "something unclear",
        "warnings": [],
    }
    with pytest.raises(FrameCompileError):
        compile_frame_to_ast(ambiguous)

    lossy = {
        "kind": "fact",
        "facts": [{"type": "entity_relation", "subject": "A", "relation": "depends_on"}],
        "source_id": "premise_9",
        "source_text": "A depends on something.",
        "premise_id": 9,
        "warnings": [],
    }
    with pytest.raises(FrameCompileError):
        compile_frame_to_ast(lossy)


def test_ast_validation_checks_unstable_arity_numeric_operands_nested_implication() -> None:
    unstable = {
        "metadata": {"source_id": "premise_1", "source_text": "x"},
        "node": {
            "type": "and",
            "values": [
                {"type": "pred", "name": "p", "args": ["a"]},
                {"type": "pred", "name": "p", "args": ["a", "b"]},
            ],
        },
    }
    with pytest.raises(ASTValidationError, match="unstable predicate arity"):
        validate_ast(unstable)

    bad_numeric = {
        "metadata": {"source_id": "premise_2", "source_text": "x"},
        "node": {"type": "compare", "op": ">=", "left": {"type": "num_ref", "entity": "Mai", "attribute": "gpa"}, "right": {"type": "pred", "name": "x", "args": []}},
    }
    with pytest.raises(ASTValidationError, match="invalid numeric operand"):
        validate_ast(bad_numeric)

    nested = {
        "metadata": {"source_id": "premise_3", "source_text": "x"},
        "node": {
            "type": "implies",
            "if": {
                "type": "implies",
                "if": {"type": "pred", "name": "a", "args": []},
                "then": {"type": "pred", "name": "b", "args": []},
            },
            "then": {"type": "pred", "name": "c", "args": []},
        },
    }
    with pytest.raises(ASTValidationError, match="nested implications"):
        validate_ast(nested)


def test_artifact_serialization_contract() -> None:
    events = [
        build_frame_event("normalized_frame", "premise_1", {"kind": "fact"}),
        build_frame_event("validated_frame", "premise_1", {"kind": "fact"}),
        build_frame_event("compiled_ast", "premise_1", {"type": "pred"}),
        build_frame_event("rejected", "premise_2", {"kind": "ambiguous"}, reason="frame_validation_error"),
    ]
    blob = serialize_frame_events_jsonl(events)
    lines = [line for line in blob.splitlines() if line.strip()]
    assert len(lines) == 4
    assert '"event_type": "normalized_frame"' in lines[0]
    assert '"event_type": "rejected"' in lines[-1]

    with pytest.raises(ArtifactContractError):
        build_frame_event("invalid_event", "premise_3", {"x": 1})
