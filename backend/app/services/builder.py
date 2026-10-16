import re
from typing import Any

from fastapi import HTTPException

from app.services.id_generator import new_uuid, now_ms

PLACEHOLDER = re.compile(r"\{\{(uuid:[^}]+|now_ms|[^}]+)\}\}")


def fill_template(value: Any, values: dict[str, Any], generated: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: fill_template(child, values, generated) for key, child in value.items()}
    if isinstance(value, list):
        return [fill_template(child, values, generated) for child in value]
    if not isinstance(value, str):
        return value

    exact = re.fullmatch(r"\{\{(uuid:[^}]+|now_ms|[^}]+)\}\}", value)
    if exact:
        token = exact.group(1)
        if token == "now_ms":
            return now_ms()
        if token.startswith("uuid:"):
            name = token[5:]
            generated.setdefault(name, new_uuid())
            return generated[name]
        if token not in values:
            raise HTTPException(status_code=422, detail=f"Missing template value for {token}.")
        return values[token]

    def replace(match: re.Match) -> str:
        token = match.group(1)
        if token == "now_ms":
            return str(now_ms())
        if token.startswith("uuid:"):
            name = token[5:]
            generated.setdefault(name, new_uuid())
            return generated[name]
        if token not in values:
            raise HTTPException(status_code=422, detail=f"Missing template value for {token}.")
        return str(values[token])

    return PLACEHOLDER.sub(replace, value)
