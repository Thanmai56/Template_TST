import json
from pathlib import Path
import re
from typing import Any

import yaml
from fastapi import HTTPException

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates"


class TemplateRegistry:
    def __init__(self, root: Path = TEMPLATE_ROOT):
        self.root = root

    def list_templates(self) -> list[dict[str, Any]]:
        entries = []
        for manifest_path in sorted(self.root.glob("*/manifest.yaml")):
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            entries.append({**manifest, "id": manifest_path.parent.name})
        return entries

    def get_template(self, template_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        self.validate_id(template_id)
        folder = self.root / template_id
        manifest_path = folder / "manifest.yaml"
        template_path = folder / "template.json"
        if not manifest_path.is_file() or not template_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"No template for {template_id} yet. Upload file A and file B in Template Lab.",
            )
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        template = json.loads(template_path.read_text(encoding="utf-8"))
        if not template:
            raise HTTPException(
                status_code=422,
                detail=f"No template for {template_id} yet. Upload file A and file B in Template Lab.",
            )
        return manifest, template

    def get_template_content(self, template_id: str) -> dict[str, Any]:
        self.validate_id(template_id)
        manifest_path = self.root / template_id / "manifest.yaml"
        template_path = self.root / template_id / "template.json"
        if not manifest_path.is_file() or not template_path.is_file():
            raise HTTPException(status_code=404, detail="Template was not found.")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        template = json.loads(template_path.read_text(encoding="utf-8"))
        if not template:
            raise HTTPException(status_code=422, detail="Template file is empty. Learn it from files A and B.")
        return {"template": template, "manifest": manifest}

    def compose_rules(self) -> dict[str, Any]:
        path = self.root / "compose_rules.yaml"
        if not path.is_file():
            raise HTTPException(status_code=500, detail="Template composition rules are missing.")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def save_template(
        self, template_id: str, manifest: dict[str, Any], template: dict[str, Any]
    ) -> None:
        self.validate_id(template_id)
        folder = self.root / template_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "template.json").write_text(
            json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (folder / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    @staticmethod
    def validate_id(template_id: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", template_id):
            raise HTTPException(status_code=422, detail="Invalid template id.")
