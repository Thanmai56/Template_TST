from pydantic import BaseModel, ConfigDict


class Field(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: str = "unknown"
    nullable: bool | None = None


class SourceTable(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    fields: list[Field]
    raw: dict
