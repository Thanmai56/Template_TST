import json
import re
from pathlib import Path
from typing import Any

import yaml

from app.domain.source import SourceTable

TOKEN = re.compile(r"\{\{[^}]+\}\}")


def _ids(value: Any, id_field: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == id_field and isinstance(child, str):
                found.append(child)
            found.extend(_ids(child, id_field))
    elif isinstance(value, list):
        for child in value:
            found.extend(_ids(child, id_field))
    return found


def validate_document(
    document: dict[str, Any], sources: list[SourceTable], golden: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None, rules: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if rules is None:
        config_path = Path(__file__).resolve().parents[1] / "templates" / "compose_rules.yaml"
        rules = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rules = rules.get("validation", {})

    def add(name: str, passed: bool, reason: str) -> None:
        checks.append({"check": name, "passed": passed, "reason": reason})

    text = json.dumps(document, ensure_ascii=False)
    add("No unfilled placeholders", TOKEN.search(text) is None,
        "No template placeholders remain." if not TOKEN.search(text) else "Unfilled template placeholder remains.")

    ui_model = _get_path(document, rules.get("ui_model_path", ""))
    ids = _ids(ui_model, rules.get("id_field", "id"))
    add("Unique UI ids", len(ids) == len(set(ids)),
        "All UI ids are unique." if len(ids) == len(set(ids)) else "Duplicate id found in uiModel.")

    definitions = _get_path(document, rules.get("definitions_path", ""))
    elements_key = rules.get("elements_key", "elements")
    element_names = {
        element
        for definition in definitions.values() if isinstance(definition, dict)
        for element in (definition.get(elements_key, {}) or {})
    } if isinstance(definitions, dict) else set()
    selected_path = rules.get("selected_columns_path", "")
    selected = _selected_columns(document, selected_path, rules)
    source_columns = _source_columns(document, selected_path, rules)
    missing_elements = sorted(selected - element_names)
    add("Selected columns exist in elements", not missing_elements,
        "All selected columns are represented in elements." if not missing_elements
        else f"Columns missing from elements: {', '.join(missing_elements)}.")

    source_fields = {source.name: {field.name for field in source.fields} for source in sources}
    source_names = set().union(*source_fields.values()) if source_fields else set()
    missing_sources = sorted(source_columns - source_names) if source_columns else []
    add("Columns exist in source tables", not missing_sources,
        "Selected columns exist in uploaded sources." if not missing_sources
        else f"Columns missing from uploaded sources: {', '.join(missing_sources)}.")

    duplicates = _duplicate_output_names(document, selected_path, rules)
    add("No duplicate output column names", not duplicates,
        "Output column names are unique." if not duplicates
        else f"Duplicate output column names: {', '.join(duplicates)}.")

    invalid_join = _invalid_join_key(document, sources, steps or [])
    add("Join keys exist and have compatible types", invalid_join is None,
        "Join key columns exist and have compatible types." if invalid_join is None else invalid_join)

    links = _links(ui_model, set(rules.get("successor_fields", [])))
    id_set = set(ids)
    broken = [link for link in links if link not in id_set]
    add("Successor links resolve", not broken,
        "All successor links point to existing UI ids." if not broken
        else f"Successor link points to missing id: {broken[0]}.")

    structure_matches = golden is None or _matches_structure(document, golden)
    add("Output structure matches golden", structure_matches,
        "Output structure preserves the golden keys." if structure_matches
        else "Output JSON keys do not match the golden structure.")
    return checks


def _get_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split(".") if path else []:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _output_name(item: dict[str, Any], rules: dict[str, Any]) -> str | None:
    reference_field = rules.get("reference_field")
    for field in rules.get("output_name_fields", []):
        if field == reference_field:
            reference = item.get(field)
            if isinstance(reference, list) and reference:
                return str(reference[-1])
        elif item.get(field) is not None:
            return str(item[field])
    return None


def _selected_columns(document: dict[str, Any], path: str, rules: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    columns = _get_path(document, path)
    for item in columns if isinstance(columns, list) else []:
        if isinstance(item, str):
            found.add(item)
        elif isinstance(item, dict):
            name = _output_name(item, rules)
            if name:
                found.add(name)
    return found


def _source_columns(document: dict[str, Any], path: str, rules: dict[str, Any]) -> set[str]:
    columns = _get_path(document, path)
    reference_field = rules.get("reference_field")
    found = set()
    for item in columns if isinstance(columns, list) else []:
        if isinstance(item, str):
            found.add(item)
        elif isinstance(item, dict):
            reference = item.get(reference_field)
            if isinstance(reference, list) and reference:
                found.add(str(reference[-1]))
            else:
                name = _output_name(item, rules)
                if name:
                    found.add(name)
    return found


def _duplicate_output_names(document: dict[str, Any], path: str, rules: dict[str, Any]) -> set[str]:
    names: list[str] = []
    columns = _get_path(document, path)
    for item in columns if isinstance(columns, list) else []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = _output_name(item, rules)
            if name:
                names.append(str(name))
    return {name for name in names if names.count(name) > 1}


def _invalid_join_key(document: dict, sources: list[SourceTable], steps: list[dict]) -> str | None:
    source_map = {source.name: {field.name: field.type for field in source.fields} for source in sources}
    for step in steps:
        if step.get("type") != "join":
            continue
        left = source_map.get(step.get("left_table"), {})
        right = source_map.get(step.get("right_table"), {})
        for pair in step.get("key_pairs", []):
            left_name, right_name = pair.get("left_column"), pair.get("right_column")
            if left_name not in left or right_name not in right:
                return f"Join key '{left_name}' or '{right_name}' does not exist on its source table."
            left_type = _type_family(left[left_name])
            right_type = _type_family(right[right_name])
            if left_type != "unknown" and right_type != "unknown" and left_type != right_type:
                return f"Join key types are incompatible: {left_type} and {right_type}."
    return None


def _type_family(field_type: str) -> str:
    name = field_type.lower().split(".")[-1]
    if any(token in name for token in ("char", "string", "text", "clob")):
        return "text"
    if any(token in name for token in ("int", "decimal", "numeric", "number", "float", "double")):
        return "number"
    if any(token in name for token in ("date", "time")):
        return "temporal"
    if any(token in name for token in ("binary", "blob", "raw")):
        return "binary"
    if name in {"unknown", ""}:
        return "unknown"
    return name


def _links(value: Any, successor_fields: set[str]) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in successor_fields and isinstance(child, str):
                result.append(child)
            result.extend(_links(child, successor_fields))
    elif isinstance(value, list):
        for child in value:
            result.extend(_links(child, successor_fields))
    return result


def _matches_structure(output: Any, golden: Any) -> bool:
    if isinstance(golden, dict):
        return isinstance(output, dict) and all(
            key in output and _matches_structure(output[key], child)
            for key, child in golden.items()
        )
    if isinstance(golden, list):
        return isinstance(output, list) and (
            not golden or all(_matches_structure(child, golden[0]) for child in output)
        )
    return type(output) is type(golden)
