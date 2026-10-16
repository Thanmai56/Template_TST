from pydantic import BaseModel, ConfigDict, Field


class KeyPair(BaseModel):
    left_column: str
    right_column: str


class PipelineStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    key_pairs: list[KeyPair] = Field(default_factory=list)


class PipelineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view_name: str = "GeneratedView"
    base_view: str | None = None
    steps: list[PipelineStep]
