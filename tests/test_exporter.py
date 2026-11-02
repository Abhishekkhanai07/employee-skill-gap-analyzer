import json

import pandas as pd

from src.export.exporter import export_all


def test_exports_csv_json_sql_ground_truth_separately_and_checksums(tmp_path):
    data = {
        "roles": pd.DataFrame([{"role_id": "ROL-000001", "role_name": "Analyst"}]),
    }
    truth = pd.DataFrame([{
        "issue_type": "known_exception",
        "entity_id": "EMP-000001",
        "expected_decision": "review",
    }])
    files = export_all(
        data=data,
        ground_truth_df=truth,
        validation_summary={"passed": True},
        outcomes={"employees": 1},
        output_dir=str(tmp_path),
        seed=20261022,
        formats=["csv", "json", "sql"],
    )

    seed_sql = (tmp_path / "seed.sql").read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / "source_manifest.json").read_text(encoding="utf-8"))
    assert "ROL-000001" in seed_sql
    assert "known_exception" not in seed_sql
    assert (tmp_path / "ground_truth.csv").is_file()
    assert (tmp_path / "ground_truth.json").is_file()
    assert (tmp_path / "validation_summary.json").is_file()
    assert (tmp_path / "outcome_summary.json").is_file()
    assert manifest["seed"] == 20261022
    assert manifest["ground_truth_rows"] == 1
    assert set(manifest["generated_files_sha256"]) == {
        "roles.csv",
        "roles.json",
        "ground_truth.csv",
        "ground_truth.json",
        "seed.sql",
        "validation_summary.json",
        "outcome_summary.json",
    }
    assert len(files) == 9
