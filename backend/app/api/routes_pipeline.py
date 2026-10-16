import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.routes_sources import SOURCES
from app.domain.pipeline import PipelineSpec
from app.domain.source import SourceTable
from app.services.builder import fill_template
from app.services.composer import apply_template, link_nodes
from app.services.template_registry import TemplateRegistry
from app.services.validator import validate_document

router = APIRouter(tags=["pipeline"])
registry = TemplateRegistry()
BUILDS: dict[str, tuple[Path, str]] = {}


@router.post("/build")
def build(spec: PipelineSpec) -> dict:
    if not SOURCES:
        raise HTTPException(status_code=422, detail="Upload source tables before building.")
    sources = [SourceTable.model_validate(source) for source in SOURCES]
    golden_dir = Path(__file__).resolve().parents[2] / "golden"
    available_golden = sorted(golden_dir.glob("*.json"))
    base = sources[0].raw
    if spec.base_view:
        requested = Path(spec.base_view).name
        golden_path = golden_dir / requested
        if golden_path.is_file():
            base = json.loads(golden_path.read_text(encoding="utf-8"))
            base_name = requested
        else:
            base_name = ""
        matches = [source for source in sources if source.name == spec.base_view]
        if not base_name and matches:
            base = matches[0].raw
        elif not base_name:
            raise HTTPException(status_code=422, detail=f"Base view '{spec.base_view}' was not found.")
    elif available_golden:
        base = json.loads(available_golden[0].read_text(encoding="utf-8"))
    output = json.loads(json.dumps(base))
    used = []
    rules = registry.compose_rules()
    for step in spec.steps:
        step_data = step.model_dump(mode="json")
        template_id = step_data.pop("type")
        manifest, template = registry.get_template(template_id)
        rendered = fill_template(template, step_data, {})
        apply_template(output, rendered, manifest.get("insert_targets", {}))
        used.append({"id": template_id, "operation": manifest.get("operation", template_id),
                     "status": manifest.get("status", "draft")})
    link_nodes(output, [], rules)
    checks = validate_document(
        output, sources, base, [step.model_dump(mode="json") for step in spec.steps], rules
    )
    build_id = str(uuid4())
    output_dir = Path(__file__).resolve().parents[2] / "builds"
    output_dir.mkdir(exist_ok=True)
    file_path = output_dir / f"{build_id}.json"
    file_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    BUILDS[build_id] = (file_path, spec.view_name)
    return {"id": build_id, "view_name": spec.view_name, "json": output,
            "validation": checks, "templates": used,
            "download_url": f"/api/build/{build_id}/download"}


@router.get("/build/{build_id}/download")
def download(build_id: str):
    build = BUILDS.get(build_id)
    if build is None or not build[0].is_file():
        raise HTTPException(status_code=404, detail="Build was not found.")
    path, view_name = build
    safe_name = "".join(char for char in view_name if char.isalnum() or char in "-_") or "GeneratedView"
    return FileResponse(path, media_type="application/json", filename=f"{safe_name}.json")
