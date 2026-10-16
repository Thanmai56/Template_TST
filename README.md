# Template Lab

Template Lab is a testing tool for composing SAP Datasphere graphical-view JSON from human-authored templates. It does not use an LLM and does not generate Datasphere structure in Python. Templates and composition rules live under `backend/app/templates/`.

## Run

Backend (from `backend/`):

```powershell
pip install -r requirements.txt
python run.py
```

Frontend (from `frontend/`):

```powershell
npm install
npm run dev
```

Open <http://localhost:5173>.

## Seven-step template workflow

1. Export file A from Datasphere before making one change.
2. Make exactly one change in Datasphere.
3. Export file B after that change.
4. Upload A and B to Template Lab and inspect the grouped JSON-path diff.
5. Name the operation, save a draft, and edit its placeholders in the template editor.
6. Select sources and pipeline steps, then build and review the validation report and JSON.
7. Download the generated JSON, import it into Datasphere, and record the import result.

## Golden exports

Put real exports such as `GV_EMPLOYEE_TENURE.json` and `IEMPLOYMENT.json` in `backend/golden/`. The projection template must be learned from the real before/after exports; no Datasphere JSON is fabricated if an export is absent. An empty or missing step template is refused with instructions to upload A and B in Template Lab.

Templates contain the copied JSON structure, placeholder values, and a `manifest.yaml`. The manifest's `insert_targets` are JSON paths used by the generic composer. Composition order and link field names are read from `compose_rules.yaml`.

## Tests

From `backend/`, run `pytest`.
