from __future__ import annotations

from typing import Any, Dict, List

from app.parse_frames import validate_parse_frame


class FrameCompileError(ValueError):
    pass


def compile_frame_to_ast(frame: Dict[str, Any]) -> Dict[str, Any]:
    validated = validate_parse_frame(frame)
    kind = validated["kind"]
    if kind == "ambiguous":
        raise FrameCompileError("ambiguous frames cannot be compiled")

    node: Dict[str, Any]
    if kind == "rule":
        node = _compile_rule(validated)
    elif kind == "fact":
        node = _compile_fact(validated)
    elif kind == "claim":
        node = _compile_slot(validated["claim"])
    elif kind == "compound":
        node = _compile_compound(validated)
    else:
        raise FrameCompileError("unsupported frame kind")

    metadata = {"source_id": validated["source_id"], "source_text": validated["source_text"]}
    if "premise_id" in validated:
        metadata["premise_id"] = validated["premise_id"]
    if "candidate_label" in validated:
        metadata["candidate_label"] = validated["candidate_label"]
    return {"metadata": metadata, "node": node, "warnings": list(validated.get("warnings", []))}


def _compile_rule(frame: Dict[str, Any]) -> Dict[str, Any]:
    antecedent = _join_nodes([_compile_slot(slot) for slot in frame["if"]], "and")
    consequent = _join_nodes([_compile_slot(slot) for slot in frame["then"]], "and")
    implies = {"type": "implies", "if": antecedent, "then": consequent}

    scope = frame.get("scope")
    if isinstance(scope, str) and scope.strip():
        var_name = scope.rstrip("s").lower() or "x"
        return {"type": "forall", "var": var_name, "body": implies}
    return implies


def _compile_fact(frame: Dict[str, Any]) -> Dict[str, Any]:
    facts = [_compile_slot(slot) for slot in frame["facts"]]
    return _join_nodes(facts, "and")


def _compile_compound(frame: Dict[str, Any]) -> Dict[str, Any]:
    operator = frame["operator"]
    operands = [_compile_slot(slot) for slot in frame["operands"]]
    return _join_nodes(operands, operator)


def _join_nodes(nodes: List[Dict[str, Any]], operator: str) -> Dict[str, Any]:
    if not nodes:
        raise FrameCompileError("cannot compile empty node list")
    if len(nodes) == 1:
        return nodes[0]
    if operator not in {"and", "or"}:
        raise FrameCompileError("invalid compound operator")
    return {"type": operator, "values": nodes}


def _compile_slot(slot: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(slot, dict):
        raise FrameCompileError("slot must be an object")

    slot_type = slot.get("type")
    if slot_type in {"predicate", "pred"}:
        pred = {
            "type": "pred",
            "name": str(slot.get("name", "")).strip() or str(slot.get("relation", "")).strip(),
            "args": [],
        }
        if not pred["name"]:
            raise FrameCompileError("predicate slot missing name/relation")
        for key in ("entity", "subject", "object", "complement"):
            value = slot.get(key)
            if value is not None:
                pred["args"].append(str(value))
        args = slot.get("args")
        if isinstance(args, list):
            pred["args"].extend(args)
        if slot.get("polarity") is False:
            return {"type": "not", "value": pred}
        return pred

    if slot_type == "numeric_value":
        return {
            "type": "compare",
            "op": "=",
            "left": {"type": "num_ref", "entity": _slot_entity(slot), "attribute": _slot_attr(slot)},
            "right": _compile_numeric_value(slot.get("value")),
        }

    if slot_type == "numeric_condition":
        right = slot.get("expression")
        if isinstance(right, dict):
            right_node = _compile_slot(right)
        else:
            right_node = _compile_numeric_value(slot.get("value"))
        return {
            "type": "compare",
            "op": slot.get("op"),
            "left": {"type": "num_ref", "entity": _slot_entity(slot), "attribute": _slot_attr(slot)},
            "right": right_node,
        }

    if slot_type == "arithmetic_expression":
        op = slot.get("op")
        operands = slot.get("operands")
        if not isinstance(operands, list):
            raise FrameCompileError("arithmetic_expression.operands must be a list")
        return {"type": "arith", "op": op, "operands": [_compile_numeric_operand(x) for x in operands]}

    if slot_type == "entity_relation":
        for key in ("subject", "relation", "object"):
            if key not in slot or slot.get(key) in (None, ""):
                raise FrameCompileError("entity_relation missing required roles")
        args = [str(slot["subject"]), str(slot["object"])]
        if slot.get("complement") is not None:
            args.append(str(slot["complement"]))
        return {"type": "pred", "name": str(slot["relation"]), "args": args}

    if slot_type in {"and", "or"}:
        values = slot.get("operands", slot.get("values"))
        if not isinstance(values, list):
            raise FrameCompileError(f"{slot_type} slot requires operands")
        return {"type": slot_type, "values": [_compile_slot(v) for v in values]}

    if slot_type == "not":
        return {"type": "not", "value": _compile_slot(slot.get("value"))}

    raise FrameCompileError(f"unsupported slot type: {slot_type}")


def _compile_numeric_operand(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict) and value.get("type") in {"num_ref", "number", "arith"}:
        if value["type"] == "number":
            return _compile_numeric_value(value.get("value"))
        if value["type"] == "num_ref":
            return {"type": "num_ref", "entity": _slot_entity(value), "attribute": _slot_attr(value)}
        return {"type": "arith", "op": value.get("op"), "operands": [_compile_numeric_operand(x) for x in value.get("operands", [])]}
    if isinstance(value, dict) and "attribute" in value:
        return {"type": "num_ref", "entity": _slot_entity(value), "attribute": _slot_attr(value)}
    return _compile_numeric_value(value)


def _compile_numeric_value(value: Any) -> Dict[str, Any]:
    if not isinstance(value, (int, float)):
        raise FrameCompileError("numeric value must be int/float")
    return {"type": "number", "value": value}


def _slot_entity(slot: Dict[str, Any]) -> str:
    value = slot.get("entity", "entity")
    return str(value)


def _slot_attr(slot: Dict[str, Any]) -> str:
    value = slot.get("attribute")
    if value is None or str(value).strip() == "":
        raise FrameCompileError("numeric slot missing attribute")
    return str(value)

