"""
Skill gap analysis and course recommendation engine for YottaFlex.

Compares employee proficiencies against role-specific targets,
recommends courses to close gaps (respecting prerequisites, budgets,
and availability), and sequences those courses into learning paths.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import config


# ---------------------------------------------------------------------------
# 1. Calculate Skill Gaps
# ---------------------------------------------------------------------------

def calculate_skill_gaps(
    employees_df: pd.DataFrame,
    role_skill_targets_df: pd.DataFrame,
    employee_skills_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compare every employee's current proficiencies against their role's
    required skill targets and return a row per (employee, skill) pair.

    For employees with multiple assessments of the same skill the **latest**
    assessment (by ``assessed_date``) is used.

    Parameters
    ----------
    employees_df : pd.DataFrame
        Columns: employee_id, role_id, department, status, …
    role_skill_targets_df : pd.DataFrame
        Columns: rst_id, role_id, skill_id, target_proficiency, priority
    employee_skills_df : pd.DataFrame
        Columns: esk_id, employee_id, skill_id, current_proficiency,
        assessed_date

    Returns
    -------
    pd.DataFrame
        Columns: employee_id, role_id, skill_id, skill_name,
        target_proficiency, current_proficiency, gap, priority
        Sorted by employee_id ASC then gap DESC.
    """
    # Handle empty inputs --------------------------------------------------
    result_cols = [
        "employee_id", "role_id", "skill_id", "skill_name",
        "target_proficiency", "current_proficiency", "gap", "priority",
    ]
    if employees_df.empty or role_skill_targets_df.empty:
        return pd.DataFrame(columns=result_cols)

    # 1. Latest assessment per (employee, skill) --------------------------
    if employee_skills_df.empty:
        latest_skills = pd.DataFrame(
            columns=["employee_id", "skill_id", "current_proficiency"]
        )
    else:
        es = employee_skills_df.copy()
        es["assessed_date"] = pd.to_datetime(es["assessed_date"])
        # Keep only the row with the maximum assessed_date per group
        idx = es.groupby(["employee_id", "skill_id"])["assessed_date"].idxmax()
        latest_skills = es.loc[idx, ["employee_id", "skill_id", "current_proficiency"]].copy()

    # 2. Build the required-skill matrix per employee ----------------------
    #    employee → role → required skills
    emp_roles = employees_df[["employee_id", "role_id"]].drop_duplicates()

    targets = emp_roles.merge(
        role_skill_targets_df[["role_id", "skill_id", "target_proficiency", "priority"]],
        on="role_id",
        how="inner",
    )

    # 3. Left-join current proficiency (may be NaN if never assessed) ------
    merged = targets.merge(
        latest_skills[["employee_id", "skill_id", "current_proficiency"]],
        on=["employee_id", "skill_id"],
        how="left",
    )
    # Employees with no assessment for a target skill get proficiency 0
    merged["current_proficiency"] = (
        merged["current_proficiency"].fillna(0).astype(int)
    )

    # 4. Compute gap -------------------------------------------------------
    merged["gap"] = np.maximum(
        0, merged["target_proficiency"] - merged["current_proficiency"]
    )

    # 5. Derive skill_name -------------------------------------------------
    #    role_skill_targets may not carry skill_name; build from skill_id.
    #    If a skills dimension table is available upstream we would join it
    #    here.  As a fallback, use the skill_id itself.
    if "skill_name" not in merged.columns:
        merged["skill_name"] = merged["skill_id"]

    # 6. Sort and select output columns ------------------------------------
    merged = merged.sort_values(
        by=["employee_id", "gap"], ascending=[True, False]
    ).reset_index(drop=True)

    return merged[result_cols]


# ---------------------------------------------------------------------------
# 2. Recommend Courses
# ---------------------------------------------------------------------------

def recommend_courses(
    skill_gaps_df: pd.DataFrame,
    course_skills_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    prerequisites_df: pd.DataFrame,
    completions_df: pd.DataFrame,
    budgets_df: pd.DataFrame,
    employees_df: pd.DataFrame,
    enrollments_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """For every skill gap > 0, recommend courses that teach the missing
    skill to at least the required target level.

    Constraints checked per recommendation:
    * **Prerequisites** – all prerequisite courses must appear in the
      employee's completed+passed records.
    * **Budget** – cumulative course cost for the employee's department
      must not exceed the department's remaining budget.
    * **Availability** – course status must be ``'active'`` and the current
      planning date must be within the course's availability window.

    Parameters
    ----------
    skill_gaps_df : pd.DataFrame
        Output of :func:`calculate_skill_gaps`.
    course_skills_df : pd.DataFrame
        Columns: csk_id, course_id, skill_id, skill_level_gained
    courses_df : pd.DataFrame
        Columns: course_id, course_name, cost, duration_hours, capacity,
        availability_start, availability_end, status
    prerequisites_df : pd.DataFrame
        Columns: prq_id, course_id, prerequisite_course_id
    completions_df : pd.DataFrame
        Columns: completion_id, enrollment_id, employee_id, course_id,
        completion_date, score, passed
    budgets_df : pd.DataFrame
        Columns: budget_id, department, year, total_budget, allocated,
        spent, remaining
    employees_df : pd.DataFrame
        Columns: employee_id, department, …

    Returns
    -------
    pd.DataFrame
        Columns: employee_id, skill_id, gap, recommended_course_id,
        course_name, course_cost, meets_prerequisites, within_budget,
        available, recommendation_rank
    """
    result_cols = [
        "employee_id", "skill_id", "gap", "recommended_course_id",
        "course_name", "course_cost", "meets_prerequisites",
        "within_budget", "available", "capacity_available",
        "recommendation_feasible", "rejection_reasons", "recommendation_rank",
    ]
    # Nothing to recommend if there are no gaps > 0
    gaps = skill_gaps_df[skill_gaps_df["gap"] > 0].copy()
    if gaps.empty or course_skills_df.empty or courses_df.empty:
        return pd.DataFrame(columns=result_cols)

    # ---- Pre-compute helpers ---------------------------------------------

    # Set of (employee_id, course_id) pairs where the employee passed
    passed_completions: set = set()
    if not completions_df.empty:
        passed = completions_df[completions_df["passed"] == True]
        passed_completions = set(
            zip(passed["employee_id"], passed["course_id"])
        )

    # Prerequisites lookup: course_id -> set of prerequisite_course_ids
    prereq_map: Dict[str, set] = {}
    if not prerequisites_df.empty:
        for cid, grp in prerequisites_df.groupby("course_id"):
            prereq_map[cid] = set(grp["prerequisite_course_id"])

    # Employee -> department mapping
    emp_dept = employees_df.set_index("employee_id")["department"].to_dict()

    # Department remaining budget for the PLANNING_YEAR (mutable tracker)
    dept_budget_remaining: Dict[str, float] = {}
    if not budgets_df.empty:
        plan_budgets = budgets_df[budgets_df["year"] == config.PLANNING_YEAR]
        for _, row in plan_budgets.iterrows():
            dept_budget_remaining[row["department"]] = float(row["remaining"])

    # Availability check helper
    planning_start = pd.Timestamp(f"{config.PLANNING_YEAR}-01-01")
    planning_end = pd.Timestamp(f"{config.PLANNING_YEAR}-12-31")

    def _is_available(course_row: pd.Series) -> bool:
        if course_row.get("status", "inactive") != "active":
            return False
        a_start = pd.Timestamp(course_row["availability_start"])
        a_end = pd.Timestamp(course_row["availability_end"])
        return a_start <= planning_end and a_end >= planning_start

    # Index courses for fast lookup
    courses_indexed = courses_df.set_index("course_id")
    enrolled_counts: Dict[str, int] = {}
    if enrollments_df is not None and not enrollments_df.empty:
        active_enrollments = enrollments_df[
            enrollments_df["status"] != "dropped"
        ]
        enrolled_counts = active_enrollments["course_id"].value_counts().to_dict()

    # ---- Find candidate courses per (skill_id) --------------------------
    # course_skills_df tells us what each course teaches
    cs = course_skills_df[["course_id", "skill_id", "skill_level_gained"]].copy()

    # Join gap rows with candidate courses on skill_id
    candidates = gaps[["employee_id", "skill_id", "gap"]].merge(
        cs, on="skill_id", how="inner",
    )

    # Only keep courses whose skill_level_gained >= target
    # We need target_proficiency; get it from gaps
    target_map = (
        gaps.drop_duplicates(subset=["employee_id", "skill_id"])
        .set_index(["employee_id", "skill_id"])["target_proficiency"]
        .to_dict()
    )
    candidates["target_proficiency"] = candidates.apply(
        lambda r: target_map.get((r["employee_id"], r["skill_id"]), 0),
        axis=1,
    )
    candidates = candidates[
        candidates["skill_level_gained"] >= candidates["target_proficiency"]
    ].copy()

    if candidates.empty:
        return pd.DataFrame(columns=result_cols)

    # ---- Evaluate constraints per candidate row --------------------------
    if candidates.empty:
        return pd.DataFrame(columns=result_cols)

    candidates = candidates.sort_values(
        ["employee_id", "skill_id", "skill_level_gained", "course_id"],
        ascending=[True, True, False, True],
    )
    budget_left = dict(dept_budget_remaining)
    allocated_courses: set = set()
    rows = []

    for (employee_id, skill_id), group in candidates.groupby(
        ["employee_id", "skill_id"], sort=True
    ):
        evaluated = []
        department = emp_dept.get(employee_id, "")
        remaining = budget_left.get(department, 0.0)
        already_selected = set()

        for _, candidate in group.iterrows():
            course_id = candidate["course_id"]
            if course_id not in courses_indexed.index:
                continue
            course = courses_indexed.loc[course_id]
            cost = float(course["cost"])
            prerequisites_met = all(
                (employee_id, prerequisite) in passed_completions
                for prerequisite in prereq_map.get(course_id, set())
            )
            available = _is_available(course)
            capacity_available = int(enrolled_counts.get(course_id, 0)) < int(course["capacity"])
            already_planned = (employee_id, course_id) in allocated_courses
            within_budget = already_planned or remaining >= cost
            evaluated.append({
                "employee_id": employee_id,
                "skill_id": skill_id,
                "gap": int(candidate["gap"]),
                "recommended_course_id": course_id,
                "course_name": course.get("course_name", course_id),
                "course_cost": cost,
                "meets_prerequisites": prerequisites_met,
                "within_budget": within_budget,
                "available": available,
                "capacity_available": capacity_available,
                "skill_level_gained": int(candidate["skill_level_gained"]),
                "_selected": False,
                "_already_planned": already_planned,
            })

        selected = next((
            item for item in evaluated
            if item["meets_prerequisites"]
            and item["within_budget"]
            and item["available"]
            and item["capacity_available"]
        ), None)
        if selected is not None:
            selected["_selected"] = True
            course_key = (employee_id, selected["recommended_course_id"])
            if course_key not in allocated_courses:
                budget_left[department] = remaining - selected["course_cost"]
                allocated_courses.add(course_key)

        # A rank-1 infeasible row is retained as a traceable exception, but is
        # explicitly excluded from the learning path.
        ordered = sorted(evaluated, key=lambda item: (
            not item["_selected"],
            not item["meets_prerequisites"],
            not item["available"],
            not item["capacity_available"],
            not item["within_budget"],
            -item["skill_level_gained"],
            item["course_cost"],
        ))
        for rank, item in enumerate(ordered, start=1):
            rejected_for = []
            if not item["meets_prerequisites"]:
                rejected_for.append("prerequisite")
            if not item["within_budget"]:
                rejected_for.append("budget")
            if not item["available"]:
                rejected_for.append("availability")
            if not item["capacity_available"]:
                rejected_for.append("capacity")
            rows.append({
                **{key: value for key, value in item.items() if not key.startswith("_")},
                "recommendation_feasible": item["_selected"],
                "rejection_reasons": "|".join(rejected_for),
                "recommendation_rank": rank,
            })

    return pd.DataFrame(rows, columns=result_cols).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Generate Learning Paths
# ---------------------------------------------------------------------------

def generate_learning_paths(
    recommendations_df: pd.DataFrame,
    prerequisites_df: pd.DataFrame,
    courses_df: pd.DataFrame,
) -> pd.DataFrame:
    """Sequence each employee's recommended courses into an ordered
    learning path that respects prerequisite dependencies.

    Parameters
    ----------
    recommendations_df : pd.DataFrame
        Output of :func:`recommend_courses` (rank-1 rows are preferred).
    prerequisites_df : pd.DataFrame
        Columns: prq_id, course_id, prerequisite_course_id
    courses_df : pd.DataFrame
        Columns: course_id, course_name, duration_hours, cost, …

    Returns
    -------
    pd.DataFrame
        Columns: employee_id, path_step, course_id, course_name,
        skill_id, estimated_start, estimated_end, cumulative_cost,
        cumulative_hours
    """
    result_cols = [
        "employee_id", "path_step", "course_id", "course_name",
        "skill_id", "estimated_start", "estimated_end",
        "cumulative_cost", "cumulative_hours",
    ]
    if recommendations_df.empty or courses_df.empty:
        return pd.DataFrame(columns=result_cols)

    # Use rank-1 recommendations only
    best = recommendations_df[
        (recommendations_df["recommendation_rank"] == 1)
        & recommendations_df.get(
            "recommendation_feasible",
            pd.Series(False, index=recommendations_df.index),
        ).astype(bool)
    ].copy()
    if best.empty:
        return pd.DataFrame(columns=result_cols)

    # Build prerequisite graph
    prereq_map: Dict[str, set] = {}
    if not prerequisites_df.empty:
        for cid, grp in prerequisites_df.groupby("course_id"):
            prereq_map[cid] = set(grp["prerequisite_course_id"])

    # Course metadata lookup
    courses_indexed = courses_df.set_index("course_id")

    # Starting date for learning paths
    path_start = pd.Timestamp(f"{config.PLANNING_YEAR}-01-01")

    all_paths = []

    for emp_id, grp in best.groupby("employee_id"):
        # Unique courses for this employee
        course_skill_map: Dict[str, str] = {}
        for _, row in grp.iterrows():
            crs_id = row["recommended_course_id"]
            # Keep first skill mapping; a course may appear for several skills
            if crs_id not in course_skill_map:
                course_skill_map[crs_id] = row["skill_id"]

        course_ids = list(course_skill_map.keys())

        # Topological sort (Kahn's algorithm) over the courses in this path
        # Only consider prerequisite edges within the employee's course set
        in_degree: Dict[str, int] = {cid: 0 for cid in course_ids}
        adj: Dict[str, list] = {cid: [] for cid in course_ids}
        course_set = set(course_ids)

        for cid in course_ids:
            for prereq in prereq_map.get(cid, set()):
                if prereq in course_set:
                    adj[prereq].append(cid)
                    in_degree[cid] += 1

        queue = sorted([c for c in course_ids if in_degree[c] == 0])
        ordered: list = []
        while queue:
            node = queue.pop(0)
            ordered.append(node)
            for neighbour in sorted(adj.get(node, [])):
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)
            queue.sort()

        # Append any remaining (circular dependency fallback)
        for cid in course_ids:
            if cid not in ordered:
                ordered.append(cid)

        # Build sequential path
        cumulative_cost = 0.0
        cumulative_hours = 0
        current_date = path_start

        for step_idx, crs_id in enumerate(ordered, start=1):
            if crs_id in courses_indexed.index:
                crs = courses_indexed.loc[crs_id]
                c_name = crs.get("course_name", crs_id)
                duration_h = int(crs.get("duration_hours", 0))
                cost = float(crs.get("cost", 0))
            else:
                c_name = crs_id
                duration_h = 0
                cost = 0.0

            est_start = current_date
            # Assume 8 working hours per day
            work_days = max(1, int(np.ceil(duration_h / 8)))
            est_end = est_start + pd.Timedelta(days=work_days)
            current_date = est_end  # next course starts after this one

            cumulative_cost += cost
            cumulative_hours += duration_h

            all_paths.append({
                "employee_id": emp_id,
                "path_step": step_idx,
                "course_id": crs_id,
                "course_name": c_name,
                "skill_id": course_skill_map.get(crs_id, ""),
                "estimated_start": est_start,
                "estimated_end": est_end,
                "cumulative_cost": cumulative_cost,
                "cumulative_hours": cumulative_hours,
            })

    if not all_paths:
        return pd.DataFrame(columns=result_cols)

    result = pd.DataFrame(all_paths)
    return result[result_cols].reset_index(drop=True)
