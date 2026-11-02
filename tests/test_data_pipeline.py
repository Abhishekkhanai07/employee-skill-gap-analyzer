import pandas as pd

import config
from main import run_generation
from src.generators.master_data import generate_all_master_data
from src.generators.relationship_data import generate_all_relationship_data
from src.validation.validators import run_all_validations


def _small_dataset(monkeypatch):
    monkeypatch.setattr(config, "NUM_EMPLOYEES", 18)
    monkeypatch.setattr(config, "NUM_SKILLS", 24)
    monkeypatch.setattr(config, "NUM_COURSES", 36)
    monkeypatch.setattr(config, "NUM_ENROLLMENTS", 24)
    monkeypatch.setattr(config, "NUM_ROLES", 8)
    master = generate_all_master_data(seed=20261022)
    transactions = generate_all_relationship_data(seed=20261022, master_data=master)
    return {**master, **transactions}


def test_small_pipeline_has_exact_volumes_valid_references_and_reproducibility(monkeypatch):
    first = _small_dataset(monkeypatch)
    second = _small_dataset(monkeypatch)

    assert len(first["employees"]) == 18
    assert len(first["skills"]) == 24
    assert len(first["courses"]) == 36
    assert len(first["enrollments"]) == 24
    for table in first:
        pd.testing.assert_frame_equal(first[table], second[table])

    results = run_all_validations(first)
    assert results["passed"], results["checks"]
    assert first["employee_skills"]["assessment_type"].isin(
        ["baseline", "post_course"]
    ).all()


def test_completion_events_are_linked_to_completed_enrollments(monkeypatch):
    data = _small_dataset(monkeypatch)
    statuses = data["enrollments"].set_index("enrollment_id")["status"]
    assert data["completions"]["enrollment_id"].isin(statuses.index).all()
    assert data["completions"]["enrollment_id"].map(statuses).eq("completed").all()


def test_end_to_end_starter_export_validates_and_keeps_ground_truth_separate(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "NUM_EMPLOYEES", 18)
    monkeypatch.setattr(config, "NUM_SKILLS", 24)
    monkeypatch.setattr(config, "NUM_COURSES", 36)
    monkeypatch.setattr(config, "NUM_ENROLLMENTS", 24)
    monkeypatch.setattr(config, "NUM_ROLES", 8)
    monkeypatch.setattr(config, "EDGE_CASES", {
        "prerequisite_violation": 2,
        "budget_exceeded": 2,
        "duplicate_completion": 2,
        "no_reassessment": 2,
        "course_unavailable": 2,
    })

    data, validation = run_generation(
        seed=20261022,
        output_dir=str(tmp_path),
        formats=["csv", "json", "sql"],
    )

    assert validation["passed"]
    assert validation["summary"]["warnings"] == 1
    assert len(data["enrollments"]) == 24
    assert (tmp_path / "source_manifest.json").is_file()
    assert (tmp_path / "validation_summary.json").is_file()
    assert "ground_truth" not in (tmp_path / "seed.sql").read_text(encoding="utf-8")
