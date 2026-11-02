"""
Career pathway analysis for YottaFlex Skill-Gap Analyzer.

Determines career readiness for the next role level and produces an
aggregate outcome summary across the entire organisation.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import config


# -- Canonical level progression -------------------------------------------
_LEVEL_ORDER = ["junior", "mid", "senior", "lead", "principal", "director"]
_LEVEL_RANK = {lvl: idx for idx, lvl in enumerate(_LEVEL_ORDER)}


# ---------------------------------------------------------------------------
# 1. Analyze Career Pathways
# ---------------------------------------------------------------------------

def analyze_career_pathways(
    employees_df: pd.DataFrame,
    roles_df: pd.DataFrame,
    skill_gaps_df: pd.DataFrame,
    learning_paths_df: pd.DataFrame,
) -> pd.DataFrame:
    """Determine each employee's readiness for the next role level.

    Progression ladder:
        junior → mid → senior → lead → principal → director

    Parameters
    ----------
    employees_df : pd.DataFrame
        Columns: employee_id, role_id, department, status, …
    roles_df : pd.DataFrame
        Columns: role_id, role_name, department, level, …
    skill_gaps_df : pd.DataFrame
        Output of ``calculate_skill_gaps``.  Columns include
        employee_id, role_id, skill_id, target_proficiency,
        current_proficiency, gap, priority.
    learning_paths_df : pd.DataFrame
        Output of ``generate_learning_paths``.  Columns include
        employee_id, path_step, course_id, cumulative_cost,
        cumulative_hours, …

    Returns
    -------
    pd.DataFrame
        Columns: employee_id, current_role, current_level, next_role,
        next_level, total_gaps, critical_gaps, courses_needed,
        estimated_cost, estimated_hours, readiness_score
    """
    result_cols = [
        "employee_id", "current_role", "current_level",
        "next_role", "next_level",
        "total_gaps", "critical_gaps", "courses_needed",
        "estimated_cost", "estimated_hours", "readiness_score",
    ]

    if employees_df.empty or roles_df.empty:
        return pd.DataFrame(columns=result_cols)

    # -- Build employee → role lookup --------------------------------------
    roles_lookup = roles_df.set_index("role_id")[["role_name", "level", "department"]].copy()
    emp_roles = employees_df[["employee_id", "role_id"]].drop_duplicates()

    # -- Pre-aggregate skill gaps per employee -----------------------------
    gap_agg: Dict[str, dict] = {}
    if not skill_gaps_df.empty:
        for emp_id, grp in skill_gaps_df.groupby("employee_id"):
            total_skills = len(grp)
            skills_met = int((grp["gap"] == 0).sum())
            total_gap_count = int((grp["gap"] > 0).sum())
            critical_gaps = int(
                ((grp["gap"] > 0) & (grp["priority"] == "critical")).sum()
            )
            readiness = (skills_met / total_skills * 100) if total_skills > 0 else 100.0
            gap_agg[emp_id] = {
                "total_gaps": total_gap_count,
                "critical_gaps": critical_gaps,
                "readiness_score": round(readiness, 2),
            }

    # -- Pre-aggregate learning path metrics per employee ------------------
    path_agg: Dict[str, dict] = {}
    if not learning_paths_df.empty:
        for emp_id, grp in learning_paths_df.groupby("employee_id"):
            path_agg[emp_id] = {
                "courses_needed": int(grp["path_step"].max()),
                "estimated_cost": float(grp["cumulative_cost"].max()),
                "estimated_hours": float(grp["cumulative_hours"].max()),
            }

    # -- Determine the next role for every employee ------------------------
    # Strategy: find a role in the same department at the next level.
    # If no such role exists, label as N/A.
    dept_level_roles: Dict[tuple, str] = {}
    for rid, rdata in roles_lookup.iterrows():
        key = (rdata["department"], rdata["level"])
        # Keep first encountered role per (department, level)
        if key not in dept_level_roles:
            dept_level_roles[key] = (rid, rdata["role_name"])

    rows = []
    for _, emp in emp_roles.iterrows():
        emp_id = emp["employee_id"]
        role_id = emp["role_id"]

        if role_id in roles_lookup.index:
            role_data = roles_lookup.loc[role_id]
            current_role = role_data["role_name"]
            current_level = role_data["level"]
            department = role_data["department"]
        else:
            current_role = role_id
            current_level = "unknown"
            department = ""

        # Determine next level
        cur_rank = _LEVEL_RANK.get(current_level, -1)
        if cur_rank >= 0 and cur_rank < len(_LEVEL_ORDER) - 1:
            next_level = _LEVEL_ORDER[cur_rank + 1]
        else:
            next_level = "N/A"

        # Find a concrete role at the next level in the same department
        if next_level != "N/A":
            next_role_info = dept_level_roles.get((department, next_level))
            next_role = next_role_info[1] if next_role_info else f"{department} {next_level}"
        else:
            next_role = "N/A"

        # Gap metrics
        g = gap_agg.get(emp_id, {
            "total_gaps": 0,
            "critical_gaps": 0,
            "readiness_score": 100.0,
        })

        # Path metrics
        p = path_agg.get(emp_id, {
            "courses_needed": 0,
            "estimated_cost": 0.0,
            "estimated_hours": 0.0,
        })

        rows.append({
            "employee_id": emp_id,
            "current_role": current_role,
            "current_level": current_level,
            "next_role": next_role,
            "next_level": next_level,
            "total_gaps": g["total_gaps"],
            "critical_gaps": g["critical_gaps"],
            "courses_needed": p["courses_needed"],
            "estimated_cost": p["estimated_cost"],
            "estimated_hours": p["estimated_hours"],
            "readiness_score": g["readiness_score"],
        })

    if not rows:
        return pd.DataFrame(columns=result_cols)

    result = pd.DataFrame(rows)
    return result[result_cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Generate Outcome Summary
# ---------------------------------------------------------------------------

def generate_outcome_summary(
    skill_gaps_df: pd.DataFrame,
    recommendations_df: pd.DataFrame,
    learning_paths_df: pd.DataFrame,
    career_pathways_df: pd.DataFrame,
    enrollments_df: pd.DataFrame,
    completions_df: pd.DataFrame,
    budgets_df: Optional[pd.DataFrame] = None,
    employee_skills_df: Optional[pd.DataFrame] = None,
) -> dict:
    """Aggregate organisation-wide metrics into a summary dictionary.

    Parameters
    ----------
    skill_gaps_df : pd.DataFrame
        Output of ``calculate_skill_gaps``.
    recommendations_df : pd.DataFrame
        Output of ``recommend_courses``.
    learning_paths_df : pd.DataFrame
        Output of ``generate_learning_paths``.
    career_pathways_df : pd.DataFrame
        Output of ``analyze_career_pathways``.
    enrollments_df : pd.DataFrame
        Columns: enrollment_id, employee_id, course_id, enrollment_date,
        status
    completions_df : pd.DataFrame
        Columns: completion_id, enrollment_id, employee_id, course_id,
        completion_date, score, passed

    Returns
    -------
    dict
        Comprehensive summary suitable for JSON export.
    """
    summary: dict = {}

    # -- Employee counts ---------------------------------------------------
    if not career_pathways_df.empty:
        summary["total_employees"] = int(
            career_pathways_df["employee_id"].nunique()
        )
    else:
        summary["total_employees"] = 0

    # -- Gap metrics -------------------------------------------------------
    if not skill_gaps_df.empty:
        emps_with_gaps = skill_gaps_df.loc[
            skill_gaps_df["gap"] > 0, "employee_id"
        ].nunique()
        summary["total_with_gaps"] = int(emps_with_gaps)

        avg_gap = skill_gaps_df["gap"].mean()
        summary["avg_gap_score"] = round(float(avg_gap), 4)

        # Employees meeting ALL targets (every gap == 0)
        emp_max_gap = skill_gaps_df.groupby("employee_id")["gap"].max()
        summary["employees_meeting_all_targets"] = int(
            (emp_max_gap == 0).sum()
        )

        # Top-10 skills with gaps (most employees with gap > 0)
        top_gaps = (
            skill_gaps_df[skill_gaps_df["gap"] > 0]
            .groupby("skill_id")
            .agg(
                employees_affected=("employee_id", "nunique"),
                avg_gap=("gap", "mean"),
            )
            .sort_values("employees_affected", ascending=False)
            .head(10)
            .reset_index()
        )
        top_gaps["avg_gap"] = top_gaps["avg_gap"].round(2)
        summary["top_10_skill_gaps"] = top_gaps.to_dict(orient="records")
    else:
        summary["total_with_gaps"] = 0
        summary["avg_gap_score"] = 0.0
        summary["employees_meeting_all_targets"] = summary["total_employees"]
        summary["top_10_skill_gaps"] = []

    # -- Recommendation metrics --------------------------------------------
    if not recommendations_df.empty:
        summary["total_courses_recommended"] = int(len(recommendations_df))
    else:
        summary["total_courses_recommended"] = 0

    # -- Learning path cost / hours ----------------------------------------
    if not learning_paths_df.empty:
        # Sum the max cumulative values per employee to get grand totals
        per_emp = learning_paths_df.groupby("employee_id").agg(
            est_cost=("cumulative_cost", "max"),
            est_hours=("cumulative_hours", "max"),
        )
        summary["total_estimated_cost"] = round(float(per_emp["est_cost"].sum()), 2)
        summary["total_estimated_hours"] = round(float(per_emp["est_hours"].sum()), 2)
    else:
        summary["total_estimated_cost"] = 0.0
        summary["total_estimated_hours"] = 0.0

    # -- Enrollment / completion rates -------------------------------------
    if not enrollments_df.empty:
        total_enrollments = len(enrollments_df)
    else:
        total_enrollments = 0

    if not completions_df.empty:
        unique_completions = completions_df.groupby("enrollment_id", as_index=False).agg(
            passed=("passed", "max")
        )
        total_completions = len(unique_completions)
        total_passed = int(unique_completions["passed"].sum())
        summary["duplicate_completion_events"] = int(
            len(completions_df) - completions_df["enrollment_id"].nunique()
        )
    else:
        total_completions = 0
        total_passed = 0
        summary["duplicate_completion_events"] = 0

    summary["completion_rate"] = (
        round(total_completions / total_enrollments, 4)
        if total_enrollments > 0
        else 0.0
    )
    summary["pass_rate"] = (
        round(total_passed / total_completions, 4)
        if total_completions > 0
        else 0.0
    )
    if employee_skills_df is not None and not employee_skills_df.empty:
        assessments = employee_skills_df.copy()
        assessments["assessed_date"] = pd.to_datetime(assessments["assessed_date"])
        assessments = assessments.sort_values(
            ["employee_id", "skill_id", "assessed_date", "esk_id"]
        )
        assessments["prior_proficiency"] = assessments.groupby(
            ["employee_id", "skill_id"]
        )["current_proficiency"].shift(1)
        post_course = assessments[assessments["assessment_type"] == "post_course"]
        measured_changes = post_course.dropna(subset=["prior_proficiency"])
        improved_assessments = int(
            (measured_changes["current_proficiency"] > measured_changes["prior_proficiency"]).sum()
        )
        summary["post_course_assessments"] = int(len(post_course))
        summary["post_course_assessments_with_prior"] = int(len(measured_changes))
        summary["post_course_assessments_with_gain"] = improved_assessments
        summary["post_course_skill_gain_rate"] = (
            round(improved_assessments / len(measured_changes), 4)
            if not measured_changes.empty
            else 0.0
        )
        summary["average_proficiency_gain"] = (
            round(float(
                (measured_changes["current_proficiency"] - measured_changes["prior_proficiency"]).mean()
            ), 2)
            if not measured_changes.empty
            else 0.0
        )
    else:
        summary["post_course_assessments"] = 0
        summary["post_course_assessments_with_prior"] = 0
        summary["post_course_assessments_with_gain"] = 0
        summary["post_course_skill_gain_rate"] = 0.0
        summary["average_proficiency_gain"] = 0.0

    # -- Budget utilisation per department ---------------------------------
    budget_util: dict = {}
    if budgets_df is not None and not budgets_df.empty:
        budget_util = {
            row["department"]: {
                "budget": round(float(row["total_budget"]), 2),
                "planned_spend": round(float(row["spent"]), 2),
                "remaining": round(float(row["remaining"]), 2),
            }
            for _, row in budgets_df.iterrows()
        }

    summary["budget_utilization_per_department"] = budget_util

    return summary
