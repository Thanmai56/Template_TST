import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.template_learner import learn_template
from app.services.template_registry import TEMPLATE_ROOT, TemplateRegistry

router = APIRouter(tags=["templates"])
registry = TemplateRegistry()
DRAFTS: dict[str, dict[str, Any]] = {}


class TemplateEdit(BaseModel):
    template: dict
    manifest: dict


class ImportResult(BaseModel):
    status: str
    error_text: str = ""


@router.get("/templates")
def get_templates() -> list[dict]:
    return registry.list_templates()


@router.get("/templates/{template_id}")
def get_template(template_id: str) -> dict:
    return registry.get_template_content(template_id)


@router.post("/templates/learn")
async def learn(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    operation: str = Form(...),
) -> dict:
    try:
        before = json.loads((await file_a.read()).decode("utf-8"))
        after = json.loads((await file_b.read()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=f"Files A and B must be valid JSON: {error}") from error
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise HTTPException(status_code=422, detail="Files A and B must each contain a JSON object.")
    operation = operation.strip()
    if not operation:
        raise HTTPException(status_code=422, detail="Operation name is required.")
    template_id = operation.lower().replace(" ", "_")
    registry.validate_id(template_id)
    learned = learn_template(before, after, operation)
    DRAFTS[template_id] = learned
    return {"id": template_id, **learned}


@router.put("/templates/{template_id}")
def save_draft(template_id: str, edit: TemplateEdit) -> dict:
    registry.validate_id(template_id)
    edit.manifest["status"] = "draft"
    registry.save_template(template_id, edit.manifest, edit.template)
    return {"id": template_id, "saved": True}


@router.post("/templates/{template_id}/status")
def update_status(template_id: str, payload: dict) -> dict:
    registry.validate_id(template_id)
    status = payload.get("status")
    if status not in {"draft", "verified", "failed"}:
        raise HTTPException(status_code=422, detail="Status must be draft, verified, or failed.")
    path = TEMPLATE_ROOT / template_id / "manifest.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Template was not found.")
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    manifest["status"] = status
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return {"id": template_id, "status": status}


@router.post("/templates/{template_id}/import-result")
def import_result(template_id: str, result: ImportResult) -> dict:
    registry.validate_id(template_id)
    if result.status not in {"verified", "failed"}:
        raise HTTPException(status_code=422, detail="Import result must be verified or failed.")
    path = TEMPLATE_ROOT / template_id / "manifest.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Template was not found.")
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    manifest["status"] = result.status
    manifest["last_import_result"] = {"status": result.status, "error_text": result.error_text}
    path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"id": template_id, "last_import_result": manifest["last_import_result"]}
