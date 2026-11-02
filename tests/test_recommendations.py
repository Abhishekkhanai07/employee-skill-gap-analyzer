import pandas as pd

from src.logic.gap_analysis import generate_learning_paths, recommend_courses


def _recommendations(courses, prerequisites=None, completions=None, budget=1000, enrollments=None):
    return recommend_courses(
        skill_gaps_df=pd.DataFrame([{
            "employee_id": "EMP-000001",
            "skill_id": "SKL-000001",
            "gap": 2,
            "target_proficiency": 3,
        }]),
        course_skills_df=pd.DataFrame([
            {"course_id": course["course_id"], "skill_id": "SKL-000001", "skill_level_gained": 4}
            for course in courses
        ]),
        courses_df=pd.DataFrame(courses),
        prerequisites_df=pd.DataFrame(
            prerequisites or [], columns=["course_id", "prerequisite_course_id"]
        ),
        completions_df=pd.DataFrame(
            completions or [], columns=["employee_id", "course_id", "passed"]
        ),
        budgets_df=pd.DataFrame([{
            "department": "Engineering",
            "year": 2026,
            "remaining": budget,
        }]),
        employees_df=pd.DataFrame([{
            "employee_id": "EMP-000001",
            "department": "Engineering",
        }]),
        enrollments_df=pd.DataFrame(
            enrollments or [], columns=["course_id", "status"]
        ),
    )


def _course(course_id, start="2026-01-01", end="2026-12-31", cost=100, capacity=10):
    return {
        "course_id": course_id,
        "course_name": course_id,
        "cost": cost,
        "duration_hours": 8,
        "capacity": capacity,
        "availability_start": start,
        "availability_end": end,
        "status": "active",
    }


def test_recommendation_requires_completed_prerequisites():
    recs = _recommendations(
        [_course("CRS-000001")],
        prerequisites=[{"course_id": "CRS-000001", "prerequisite_course_id": "CRS-000002"}],
    )

    assert not recs.iloc[0]["meets_prerequisites"]
    assert not recs.iloc[0]["recommendation_feasible"]
    assert "prerequisite" in recs.iloc[0]["rejection_reasons"]
    assert generate_learning_paths(
        recs,
        pd.DataFrame(columns=["course_id", "prerequisite_course_id"]),
        pd.DataFrame([_course("CRS-000001")]),
    ).empty


def test_recommendation_rejects_unavailable_over_budget_and_full_courses():
    unavailable = _recommendations([_course("CRS-000001", start="2027-01-01", end="2027-12-31")])
    over_budget = _recommendations([_course("CRS-000002", cost=200)], budget=100)
    full = _recommendations(
        [_course("CRS-000003", capacity=1)],
        enrollments=[{"course_id": "CRS-000003", "status": "enrolled"}],
    )

    assert not unavailable.iloc[0]["available"]
    assert not unavailable.iloc[0]["recommendation_feasible"]
    assert not over_budget.iloc[0]["within_budget"]
    assert not over_budget.iloc[0]["recommendation_feasible"]
    assert not full.iloc[0]["capacity_available"]
    assert not full.iloc[0]["recommendation_feasible"]


def test_feasible_course_is_selected_and_sequenced():
    recs = _recommendations([_course("CRS-000004")])
    path = generate_learning_paths(
        recs,
        pd.DataFrame(columns=["course_id", "prerequisite_course_id"]),
        pd.DataFrame([_course("CRS-000004")]),
    )

    assert recs.iloc[0]["recommendation_feasible"]
    assert len(path) == 1
    assert path.iloc[0]["course_id"] == "CRS-000004"
