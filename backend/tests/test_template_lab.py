from fastapi import HTTPException

from app.domain.source import Field, SourceTable
from app.services.template_learner import learn_template
from app.services.template_registry import TemplateRegistry
from app.services.validator import validate_document


def source(name: str, fields: dict[str, str]) -> SourceTable:
    return SourceTable(
        name=name,
        fields=[Field(name=field_name, type=field_type) for field_name, field_type in fields.items()],
        raw={},
    )


def test_learner_groups_changes_and_parameterizes_generated_values():
    before = {"query": {"SELECT": {"where": []}}, "definitions": {}, "uiModel": {"id": "before"}}
    after = {
        "query": {"SELECT": {"where": [{"ref": ["EMPLOYEE"], "val": "A"}]}},
        "definitions": {"View": {"elements": {"NAME": {"type": "String"}}}},
        "uiModel": {"id": "2cb19cf4-cd61-4abd-910f-d98a82ca0001", "createdAt": 1700000000000},
    }

    learned = learn_template(before, after, "projection")

    assert learned["diff"]["query"][0]["path"].startswith("$.query.")
    assert learned["diff"]["elements"][0]["path"].startswith("$.definitions.")
    assert learned["diff"]["uiModel"]
    assert "{{uuid:id_1}}" in str(learned["template"])
    assert "{{now_ms}}" in str(learned["template"])


def test_empty_template_is_refused_with_template_lab_instructions(tmp_path):
    folder = tmp_path / "filter"
    folder.mkdir()
    (folder / "manifest.yaml").write_text("operation: filter\nstatus: draft\n", encoding="utf-8")
    (folder / "template.json").write_text("{}", encoding="utf-8")

    try:
        TemplateRegistry(tmp_path).get_template("filter")
    except HTTPException as error:
        assert error.status_code == 422
        assert error.detail == "No template for filter yet. Upload file A and file B in Template Lab."
    else:
        raise AssertionError("An empty template must not be used for a build.")


def test_validator_reports_missing_column_duplicate_id_broken_link_and_placeholder():
    document = {
        "query": {"SELECT": {"columns": ["MISSING", "EMP_ID", "EMP_ID"]}},
        "definitions": {"View": {"elements": {"EMP_ID": {"type": "Integer"}}}},
        "uiModel": {
            "nodes": [
                {"id": "same", "successorNode": "absent"},
                {"id": "same", "value": "{{column}}"},
            ]
        },
    }

    checks = validate_document(document, [source("EMPLOYEE", {"EMP_ID": "Integer"})])

    failed = {check["check"] for check in checks if not check["passed"]}
    assert {
        "No unfilled placeholders",
        "Unique UI ids",
        "Columns exist in source tables",
        "No duplicate output column names",
        "Successor links resolve",
    } <= failed


def test_combined_join_projection_filter_passes_validator():
    base = {
        "query": {"SELECT": {"columns": ["EMP_ID", "DEPT_ID"]}},
        "definitions": {
            "View": {"elements": {"EMP_ID": {"type": "Integer"}, "DEPT_ID": {"type": "Integer"}}}
        },
        "uiModel": {"nodes": [{"id": "source"}, {"id": "join"}, {"id": "projection"}, {"id": "filter"}]},
    }
    sources = [
        source("EMPLOYEE", {"EMP_ID": "Integer", "DEPT_ID": "Integer"}),
        source("DEPARTMENT", {"DEPT_ID": "Integer"}),
    ]
    steps = [
        {"type": "join", "left_table": "EMPLOYEE", "right_table": "DEPARTMENT",
         "join_type": "inner", "key_pairs": [{"left_column": "DEPT_ID", "right_column": "DEPT_ID"}]},
        {"type": "projection", "keep_columns": ["EMP_ID", "DEPT_ID"], "renames": {}},
        {"type": "filter", "column": "EMP_ID", "operator": ">", "values": [0]},
    ]

    checks = validate_document(base, sources, base, steps)

    assert all(check["passed"] for check in checks), checks


def test_validator_rejects_incompatible_join_types():
    checks = validate_document(
        {
            "query": {"SELECT": {"columns": []}},
            "definitions": {"View": {"elements": {}}},
            "uiModel": {"nodes": []},
        },
        [source("LEFT", {"KEY": "String"}), source("RIGHT", {"KEY": "Integer"})],
        steps=[
            {"type": "join", "left_table": "LEFT", "right_table": "RIGHT",
             "key_pairs": [{"left_column": "KEY", "right_column": "KEY"}]}
        ],
    )

    join_check = next(check for check in checks if check["check"] == "Join keys exist and have compatible types")
    assert not join_check["passed"]
