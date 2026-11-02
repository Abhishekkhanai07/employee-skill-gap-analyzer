import pandas as pd

from src.logic.learning_paths import generate_outcome_summary


def test_outcome_summary_measures_post_course_skill_change_separately():
    employee_skills = pd.DataFrame([
        {
            "esk_id": "ESK-000001",
            "employee_id": "EMP-000001",
            "skill_id": "SKL-000001",
            "current_proficiency": 2,
            "assessed_date": "2026-01-01",
            "assessment_type": "baseline",
        },
        {
            "esk_id": "ESK-000002",
            "employee_id": "EMP-000001",
            "skill_id": "SKL-000001",
            "current_proficiency": 3,
            "assessed_date": "2026-02-01",
            "assessment_type": "post_course",
        },
        {
            "esk_id": "ESK-000003",
            "employee_id": "EMP-000001",
            "skill_id": "SKL-000001",
            "current_proficiency": 3,
            "assessed_date": "2026-03-01",
            "assessment_type": "post_course",
        },
        {
            "esk_id": "ESK-000004",
            "employee_id": "EMP-000001",
            "skill_id": "SKL-000002",
            "current_proficiency": 4,
            "assessed_date": "2026-02-01",
            "assessment_type": "post_course",
        },
    ])
    empty = pd.DataFrame()

    summary = generate_outcome_summary(
        skill_gaps_df=empty,
        recommendations_df=empty,
        learning_paths_df=empty,
        career_pathways_df=empty,
        enrollments_df=empty,
        completions_df=empty,
        employee_skills_df=employee_skills,
    )

    assert summary["post_course_assessments"] == 3
    assert summary["post_course_assessments_with_prior"] == 2
    assert summary["post_course_assessments_with_gain"] == 1
    assert summary["post_course_skill_gain_rate"] == 0.5
    assert summary["average_proficiency_gain"] == 0.5
