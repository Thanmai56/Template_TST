import re
from typing import Any


UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def _diff(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "old": before, "new": after}]
    if isinstance(before, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            child = f"{path}.{key}"
            if key not in before:
                result.append({"path": child, "old": None, "new": after[key]})
            elif key not in after:
                result.append({"path": child, "old": before[key], "new": None})
            else:
                result.extend(_diff(before[key], after[key], child))
        return result
    if isinstance(before, list):
        result = []
        for index in range(max(len(before), len(after))):
            child = f"{path}[{index}]"
            if index >= len(before):
                result.append({"path": child, "old": None, "new": after[index]})
            elif index >= len(after):
                result.append({"path": child, "old": before[index], "new": None})
            else:
                result.extend(_diff(before[index], after[index], child))
        return result
    if before != after:
        return [{"path": path, "old": before, "new": after}]
    return []


def _parameterize(value: Any, ids: dict[str, str], key: str = "") -> Any:
    if isinstance(value, dict):
        return {child_key: _parameterize(child, ids, child_key) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_parameterize(child, ids, key) for child in value]
    if isinstance(value, str):
        if UUID_PATTERN.match(value):
            return "{{uuid:" + ids.setdefault(value, f"id_{len(ids) + 1}") + "}}"
    if isinstance(value, (int, float)) and any(
        marker in key.lower() for marker in ("timestamp", "createdat", "updatedat", "modifiedat")
    ):
        return "{{now_ms}}"
    return value


def _part(path: str) -> str:
    if path == "$.query" or path.startswith("$.query."):
        return "query"
    if (
        path == "$.uiModel"
        or path.startswith("$.uiModel.")
        or path == "$.editorSettings"
        or path.startswith("$.editorSettings.")
        or ".uiModel." in path
    ):
        return "uiModel"
    if ".elements." in path or path.endswith(".elements") or path.startswith("$.definitions."):
        return "elements"
    return "other"


def learn_template(before: dict, after: dict, operation: str) -> dict:
    changes = _diff(before, after)
    fragments: dict[str, dict[str, Any]] = {"query": {}, "elements": {}, "uiModel": {}}
    ids: dict[str, str] = {}
    for change in changes:
        path = change["path"]
        part = _part(path)
        fragments.setdefault(part, {})[path] = _parameterize(change["new"], ids)
    template = {"changes": fragments}
    grouped = {part: [change for change in changes if _part(change["path"]) == part]
               for part in ("query", "elements", "uiModel")}
    placeholders = sorted(set(re.findall(r"\{\{([^}]+)\}\}", str(template))))
    return {
        "template": template,
        "diff": grouped,
        "changed_paths": changes,
        "manifest": {
            "operation": operation,
            "status": "draft",
            "placeholders": [
                {
                    "name": placeholder,
                    "type": "generated" if placeholder.startswith(("uuid:", "now_ms")) else "value",
                    "description": "Generated value" if placeholder.startswith(("uuid:", "now_ms"))
                    else "Set this value before building.",
                }
                for placeholder in placeholders
            ],
            "insert_targets": {"changes": "$"},
            "notes": "Review changed values and add placeholders before building.",
            "last_import_result": None,
        },
    }
