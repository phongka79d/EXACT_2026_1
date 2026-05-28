from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Set, Tuple

AST_NODE_TYPES = {
    "pred",
    "not",
    "and",
    "or",
    "implies",
    "forall",
    "exists",
    "compare",
    "arith",
    "num_ref",
    "number",
    "var",
}


class ASTValidationError(ValueError):
    pass


def validate_ast(ast: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(ast, dict):
        raise ASTValidationError("ast root must be an object")
    metadata = ast.get("metadata")
    if not isinstance(metadata, dict):
        raise ASTValidationError("root metadata is required")
    _require_meta_str(metadata, "source_id")
    _require_meta_str(metadata, "source_text")

    bound: Set[str] = set()
    arity: defaultdict[str, Set[int]] = defaultdict(set)
    _validate_node(ast.get("node"), bound, arity, inside_implication=False)

    unstable = [name for name, values in arity.items() if len(values) > 1]
    if unstable:
        raise ASTValidationError(f"unstable predicate arity: {sorted(unstable)}")
    return ast


def _validate_node(
    node: Dict[str, Any], bound: Set[str], arity: defaultdict[str, Set[int]], inside_implication: bool
) -> None:
    if not isinstance(node, dict):
        raise ASTValidationError("node must be an object")
    node_type = node.get("type")
    if node_type not in AST_NODE_TYPES:
        raise ASTValidationError("invalid node type")

    if node_type == "pred":
        name = node.get("name")
        if not isinstance(name, str) or not name:
            raise ASTValidationError("pred.name is required")
        args = node.get("args", [])
        if not isinstance(args, list):
            raise ASTValidationError("pred.args must be a list")
        arity[name].add(len(args))
        for arg in args:
            _validate_term(arg, bound)
        return

    if node_type == "not":
        _validate_node(node.get("value"), bound, arity, inside_implication)
        return

    if node_type in {"and", "or"}:
        values = node.get("values")
        if not isinstance(values, list) or not values:
            raise ASTValidationError(f"{node_type}.values must be a non-empty list")
        for value in values:
            _validate_node(value, bound, arity, inside_implication)
        return

    if node_type == "implies":
        left = node.get("if")
        right = node.get("then")
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ASTValidationError("implies must include if/then nodes")
        if left.get("type") == "implies":
            raise ASTValidationError("malformed nested implications in antecedent")
        _validate_node(left, bound, arity, inside_implication=True)
        _validate_node(right, bound, arity, inside_implication=True)
        return

    if node_type in {"forall", "exists"}:
        var = node.get("var")
        if not isinstance(var, str) or not var:
            raise ASTValidationError(f"{node_type}.var is required")
        extended = set(bound)
        extended.add(var)
        _validate_node(node.get("body"), extended, arity, inside_implication)
        return

    if node_type == "compare":
        op = node.get("op")
        if op not in {"=", "!=", ">", "<", ">=", "<="}:
            raise ASTValidationError("invalid compare operator")
        _validate_numeric_term(node.get("left"), bound)
        _validate_numeric_term(node.get("right"), bound)
        return

    if node_type == "arith":
        op = node.get("op")
        if op not in {"+", "-", "*", "/", "percentage_of"}:
            raise ASTValidationError("invalid arith operator")
        operands = node.get("operands")
        if not isinstance(operands, list) or len(operands) < 2:
            raise ASTValidationError("arith.operands must have at least 2 terms")
        for operand in operands:
            _validate_numeric_term(operand, bound)
        return

    if node_type == "num_ref":
        _require_str(node, "entity")
        _require_str(node, "attribute")
        return

    if node_type == "number":
        value = node.get("value")
        if not isinstance(value, (int, float)):
            raise ASTValidationError("number.value must be numeric")
        return

    if node_type == "var":
        name = node.get("name")
        if not isinstance(name, str) or not name:
            raise ASTValidationError("var.name is required")
        if name not in bound:
            raise ASTValidationError(f"unbound variable: {name}")


def _validate_term(term: Any, bound: Set[str]) -> None:
    if isinstance(term, dict):
        term_type = term.get("type")
        if term_type == "var":
            _validate_node(term, bound, defaultdict(set), inside_implication=False)
            return
        if term_type in {"number", "num_ref", "arith"}:
            _validate_numeric_term(term, bound)
            return
    if isinstance(term, (str, int, float)):
        return
    raise ASTValidationError("invalid predicate argument")


def _validate_numeric_term(term: Any, bound: Set[str]) -> None:
    if not isinstance(term, dict):
        raise ASTValidationError("numeric term must be an object")
    term_type = term.get("type")
    if term_type == "number":
        value = term.get("value")
        if not isinstance(value, (int, float)):
            raise ASTValidationError("number.value must be numeric")
        return
    if term_type == "num_ref":
        _require_str(term, "entity")
        _require_str(term, "attribute")
        return
    if term_type == "var":
        name = term.get("name")
        if not isinstance(name, str) or not name:
            raise ASTValidationError("var.name is required")
        if name not in bound:
            raise ASTValidationError(f"unbound variable: {name}")
        return
    if term_type == "arith":
        op = term.get("op")
        if op not in {"+", "-", "*", "/", "percentage_of"}:
            raise ASTValidationError("invalid arith operator")
        operands = term.get("operands")
        if not isinstance(operands, list) or len(operands) < 2:
            raise ASTValidationError("arith.operands must have at least 2 terms")
        for operand in operands:
            _validate_numeric_term(operand, bound)
        return
    raise ASTValidationError("invalid numeric operand")


def _require_meta_str(metadata: Dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ASTValidationError(f"metadata.{key} is required")
    return value


def _require_str(node: Dict[str, Any], key: str) -> str:
    value = node.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ASTValidationError(f"{key} is required")
    return value

