from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from app.domain.source import Field, SourceTable


def parse_source(data: dict[str, Any], fallback_name: str = "Source") -> SourceTable:
    """Read common entity/table export shapes while keeping the original JSON."""
    config_path = Path(__file__).resolve().parents[1] / "templates" / "compose_rules.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")).get("source_json", {})
    name = str(_first(data, config.get("name_fields", [])) or fallback_name)
    raw_fields = data.get(config.get("fields_path"))
    if raw_fields is None:
        raw_fields = data.get(config.get("columns_path"))

    if raw_fields is None:
        definitions = data.get(config.get("definitions_path"))
        if isinstance(definitions, Mapping) and definitions:
            name, entity = next(iter(definitions.items()))
            elements = entity.get(config.get("elements_key"), {}) if isinstance(entity, Mapping) else {}
            raw_fields = [
                {"name": field_name, **(dict(spec) if isinstance(spec, Mapping) else {})}
                for field_name, spec in elements.items()
            ]
    if raw_fields is None:
        raise ValueError("No source fields were found in the uploaded JSON.")

    fields: list[Field] = []
    if isinstance(raw_fields, Mapping):
        iterable = [
            {"name": field_name, **(dict(spec) if isinstance(spec, Mapping) else {})}
            for field_name, spec in raw_fields.items()
        ]
    elif isinstance(raw_fields, list):
        iterable = raw_fields
    else:
        raise ValueError("Source fields or columns must be a JSON object or array.")

    for item in iterable:
        if not isinstance(item, Mapping):
            raise ValueError("Each source field must be a JSON object.")
        field_name = _first(item, config.get("field_name_fields", []))
        if not field_name:
            raise ValueError("Each source field must have a name.")
        field_type = _first(item, config.get("field_type_fields", [])) or "unknown"
        fields.append(
            Field(
                name=str(field_name),
                type=str(field_type),
                nullable=item.get(config.get("nullable_field")),
            )
        )
    return SourceTable(name=name, fields=fields, raw=data)


def _first(value: Mapping, keys: list[str]) -> Any:
    return next((value[key] for key in keys if value.get(key) is not None), None)
