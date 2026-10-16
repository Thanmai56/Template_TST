import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.source_parser import parse_source

router = APIRouter(tags=["sources"])
SOURCES: list[dict[str, Any]] = []


@router.post("/sources")
async def upload_sources(files: list[UploadFile] = File(...)) -> list[dict[str, Any]]:
    if not 1 <= len(files) <= 3:
        raise HTTPException(status_code=422, detail="Upload between 1 and 3 source JSON files.")
    parsed = []
    try:
        for file in files:
            data = json.loads((await file.read()).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{file.filename} must contain a JSON object.")
            parsed.append(parse_source(data, file.filename or "Source"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"Invalid source JSON: {error}") from error
    SOURCES[:] = [source.model_dump() for source in parsed]
    return SOURCES


@router.get("/sources")
def get_sources() -> list[dict[str, Any]]:
    return SOURCES


@router.get("/golden")
def get_golden_views() -> list[str]:
    folder = Path(__file__).resolve().parents[2] / "golden"
    return sorted(path.name for path in folder.glob("*.json"))
