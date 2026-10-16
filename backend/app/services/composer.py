import copy
from typing import Any

from fastapi import HTTPException


def _parts(path: str) -> list[str | int]:
    parts: list[str | int] = []
    token = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            if token:
                parts.append(token)
                token = ""
        elif char == "[":
            if token:
                parts.append(token)
                token = ""
            end = path.find("]", index)
            if end < 0 or not path[index + 1:end].isdigit():
                raise ValueError(f"Invalid JSON path: {path}")
            parts.append(int(path[index + 1:end]))
            index = end
        else:
            token += char
        index += 1
    if token:
        parts.append(token)
    return parts


def set_path(document: dict, path: str, value: Any) -> None:
    parts = _parts(path.lstrip("$.")) if path != "$" else []
    if not parts:
        if not isinstance(value, dict):
            raise HTTPException(status_code=422, detail="A root template insertion must be an object.")
        document.update(copy.deepcopy(value))
        return
    current: Any = document
    for position, part in enumerate(parts[:-1]):
        next_part = parts[position + 1]
        if isinstance(part, int):
            if isinstance(current, list) and part == len(current):
                current.append([] if isinstance(next_part, int) else {})
            current = current[part]
        else:
            if part not in current:
                current[part] = [] if isinstance(next_part, int) else {}
            current = current[part]
    key = parts[-1]
    if isinstance(key, int):
        if isinstance(current, list) and key == len(current):
            current.append(copy.deepcopy(value))
        else:
            current[key] = copy.deepcopy(value)
    elif key in current and isinstance(current[key], list) and isinstance(value, list):
        current[key].extend(copy.deepcopy(value))
    elif key in current and isinstance(current[key], dict) and isinstance(value, dict):
        current[key].update(copy.deepcopy(value))
    else:
        current[key] = copy.deepcopy(value)


def apply_template(document: dict, rendered: dict, targets: dict[str, str]) -> dict:
    if "changes" in rendered and isinstance(rendered["changes"], dict):
        for path, value in rendered["changes"].items():
            set_path(document, path, value)
        return document
    for fragment, path in targets.items():
        if fragment in rendered:
            set_path(document, path, rendered[fragment])
    return document


def link_nodes(document: dict, node_ids: list[str], rules: dict[str, Any]) -> None:
    """Rebuild configured successor fields without assuming Datasphere object paths."""
    rules = rules.get("links", rules)
    model_path = rules.get("ui_model_path")
    nodes_path = rules.get("nodes_path")
    if not model_path or not nodes_path:
        return
    current: Any = document
    for part in _parts(model_path):
        current = current[part] if isinstance(part, int) else current.get(part, {})
    for part in _parts(nodes_path):
        current = current[part] if isinstance(part, int) else current.get(part, {})
    if not isinstance(current, list):
        return
    successor_node = rules.get("successor_node_field")
    id_field = rules.get("node_id_field", "id")
    node_ids = [node.get(id_field) for node in current
                if isinstance(node, dict) and isinstance(node.get(id_field), str)]
    for index, node in enumerate(current):
        if not isinstance(node, dict):
            continue
        next_id = node_ids[index + 1] if index + 1 < len(node_ids) else None
        if successor_node and successor_node in node:
            node[successor_node] = next_id
