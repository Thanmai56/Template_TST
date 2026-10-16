from pydantic import BaseModel, ConfigDict


class TemplateMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    operation: str
    status: str
    placeholders: list[dict]
    insert_targets: dict
    notes: str = ""
    last_import_result: dict | None = None
