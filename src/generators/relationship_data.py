"""Generate dependent and transactional records from valid parent IDs."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

import config


def _random_date(rng: np.random.Generator, start: str, end: str) -> str:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    return (first + timedelta(days=int(rng.integers(0, (last - first).days + 1)))).isoformat()


def generate_role_skill_targets(
    rng: np.random.Generator, roles: pd.DataFrame, skills: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    low, high = config.ROLE_SKILL_TARGETS_PER_ROLE
    for role in roles.itertuples(index=False):
        count = min(int(rng.integers(low, high + 1)), len(skills))
        chosen = rng.choice(skills["skill_id"].to_numpy(), size=count, replace=False)
        for skill_id in chosen:
            rows.append({
                "rst_id": f"RST-{len(rows) + 1:06d}",
                "role_id": role.role_id,
                "skill_id": str(skill_id),
                "target_proficiency": int(rng.integers(2, 6)),
                "priority": str(rng.choice(
                    ["critical", "high", "medium", "low"],
                    p=[0.15, 0.35, 0.35, 0.15],
                )),
            })
    return pd.DataFrame(rows, columns=[
        "rst_id", "role_id", "skill_id", "target_proficiency", "priority",
    ])


def generate_employee_skills(
    rng: np.random.Generator,
    employees: pd.DataFrame,
    skills: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    role_skills = targets.groupby("role_id")["skill_id"].apply(list).to_dict()
    skill_ids = skills["skill_id"].to_numpy()
    low, high = config.EMPLOYEE_SKILLS_PER_EMP
    rows: list[dict[str, Any]] = []
    for employee in employees.itertuples(index=False):
        role_skill_ids = role_skills.get(employee.role_id, [])
        count = min(int(rng.integers(low, high + 1)), len(skill_ids))
        preferred_count = min(count, len(role_skill_ids))
        chosen = set()
        if preferred_count:
            chosen.update(rng.choice(role_skill_ids, size=preferred_count, replace=False).tolist())
        remaining = count - len(chosen)
        if remaining:
            pool = np.array([skill for skill in skill_ids if skill not in chosen], dtype=object)
            chosen.update(rng.choice(pool, size=remaining, replace=False).tolist())
        for skill_id in sorted(chosen):
            rows.append({
                "esk_id": f"ESK-{len(rows) + 1:06d}",
                "employee_id": employee.employee_id,
                "skill_id": str(skill_id),
                "current_proficiency": int(rng.integers(1, 6)),
                "assessed_date": _random_date(
                    rng, *config.BASELINE_ASSESSMENT_DATE_RANGE
                ),
                "assessment_type": "baseline",
                "source_completion_id": None,
            })
    return pd.DataFrame(rows, columns=[
        "esk_id", "employee_id", "skill_id", "current_proficiency",
        "assessed_date", "assessment_type", "source_completion_id",
    ])


def generate_course_skills(
    rng: np.random.Generator, courses: pd.DataFrame, skills: pd.DataFrame
) -> pd.DataFrame:
    skill_ids = skills["skill_id"].to_numpy()
    low, high = config.COURSE_SKILLS_PER_COURSE
    rows: list[dict[str, Any]] = []
    for course_index, course in enumerate(courses.itertuples(index=False)):
        count = min(int(rng.integers(low, high + 1)), len(skill_ids))
        chosen = set()
        # Guarantee coverage so every skill can be matched to at least one course.
        chosen.add(skill_ids[course_index % len(skill_ids)])
        if count > 1:
            pool = np.array([skill for skill in skill_ids if skill not in chosen], dtype=object)
            chosen.update(rng.choice(pool, size=count - 1, replace=False).tolist())
        for skill_id in sorted(chosen):
            rows.append({
                "csk_id": f"CSK-{len(rows) + 1:06d}",
                "course_id": course.course_id,
                "skill_id": str(skill_id),
                "skill_level_gained": int(rng.integers(1, 6)),
            })
    return pd.DataFrame(rows, columns=[
        "csk_id", "course_id", "skill_id", "skill_level_gained",
    ])


def generate_prerequisites(
    rng: np.random.Generator, courses: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    prior_courses = courses["course_id"].tolist()
    depth: dict[str, int] = {}
    for index, course_id in enumerate(prior_courses):
        depth[course_id] = 0
        if index == 0 or rng.random() >= 0.22:
            continue
        candidates = prior_courses[:index]
        prerequisite = str(rng.choice(candidates))
        if depth[prerequisite] >= config.PREREQUISITE_CHAIN_MAX_DEPTH:
            continue
        depth[course_id] = depth[prerequisite] + 1
        rows.append({
            "prq_id": f"PRQ-{len(rows) + 1:06d}",
            "course_id": course_id,
            "prerequisite_course_id": prerequisite,
        })
    return pd.DataFrame(rows, columns=[
        "prq_id", "course_id", "prerequisite_course_id",
    ])


def generate_enrollments_and_completions(
    rng: np.random.Generator,
    employees: pd.DataFrame,
    courses: pd.DataFrame,
    prerequisites: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create capacity-safe enrollments with prerequisite completion history."""
    num = config.NUM_ENROLLMENTS
    employees = employees.reset_index(drop=True)
    if employees.empty:
        raise ValueError("Cannot create enrollments without employees.")

    start_bound = date.fromisoformat(config.ENROLLMENT_DATE_RANGE[0])
    end_bound = date.fromisoformat(config.ENROLLMENT_DATE_RANGE[1])
    planning_courses = courses[
        (courses["status"] == "active")
        & (pd.to_datetime(courses["availability_start"]).dt.date <= end_bound)
        & (pd.to_datetime(courses["availability_end"]).dt.date >= start_bound)
    ].copy()
    if planning_courses.empty:
        raise ValueError("No active courses are available during the enrollment period.")
    course_capacities = planning_courses.set_index("course_id")["capacity"].astype(int).to_dict()
    course_availability = {
        course_id: (
            date.fromisoformat(availability_start),
            date.fromisoformat(availability_end),
        )
        for course_id, availability_start, availability_end in planning_courses[
            ["course_id", "availability_start", "availability_end"]
        ].itertuples(index=False, name=None)
    }
    prereq_map: dict[str, set[str]] = {}
    if not prerequisites.empty:
        prereq_map = prerequisites.groupby("course_id")["prerequisite_course_id"].apply(set).to_dict()
    prerequisite_course_ids = set(prerequisites["prerequisite_course_id"]) if not prerequisites.empty else set()
    roots = [
        course_id for course_id in planning_courses["course_id"]
        if course_id not in prereq_map
    ]
    prerequisite_roots = [course_id for course_id in roots if course_id in prerequisite_course_ids]
    root_pool = prerequisite_roots or roots
    if not root_pool:
        raise ValueError("No active prerequisite-free course is available during the enrollment period.")

    courses_per_employee, remainder = divmod(num, len(employees))
    employee_order = rng.permutation(len(employees)).tolist()
    planned_per_course = {course_id: 0 for course_id in planning_courses["course_id"]}
    enrollment_rows: list[dict[str, Any]] = []
    completion_rows: list[dict[str, Any]] = []
    enrollment_event_rows: list[dict[str, Any]] = []
    for position, employee_index in enumerate(employee_order):
        employee_id = employees.iloc[employee_index]["employee_id"]
        assigned_count = courses_per_employee + (position < remainder)
        completed_courses: set[str] = set()
        completed_on: dict[str, date] = {}
        selected_courses: set[str] = set()

        for slot in range(assigned_count):
            eligible = [
                course_id for course_id in planning_courses["course_id"]
                if course_id not in selected_courses
                and planned_per_course[course_id] < course_capacities[course_id]
                and prereq_map.get(course_id, set()).issubset(completed_courses)
                and (
                    not prereq_map.get(course_id)
                    or max(completed_on[parent] for parent in prereq_map[course_id])
                    + timedelta(days=1)
                    <= min(
                        end_bound,
                        course_availability[course_id][1],
                    )
                )
            ]
            if slot == 0:
                eligible = [course_id for course_id in eligible if course_id in root_pool]
            elif any(prereq_map.get(course_id) for course_id in eligible):
                eligible = [course_id for course_id in eligible if prereq_map.get(course_id)]
            if not eligible:
                eligible = [
                    course_id for course_id in root_pool
                    if course_id not in selected_courses
                    and planned_per_course[course_id] < course_capacities[course_id]
                ]
            if not eligible:
                raise ValueError(
                    f"Insufficient course capacity to generate the requested {num} enrollments."
                )
            least_used = min(planned_per_course[course_id] for course_id in eligible)
            least_used_courses = [
                course_id for course_id in eligible
                if planned_per_course[course_id] == least_used
            ]
            course_id = str(rng.choice(least_used_courses))
            selected_courses.add(course_id)
            planned_per_course[course_id] += 1
            availability_start, availability_end = course_availability[course_id]
            start = max(start_bound, availability_start)
            if prereq_map.get(course_id):
                start = max(
                    start,
                    max(completed_on[parent] for parent in prereq_map[course_id])
                    + timedelta(days=1),
                )
            end = min(end_bound, availability_end)
            enrollment_date = _random_date(rng, start.isoformat(), end.isoformat())
            enrollment_id = f"ENR-{employee_id}-{course_id}"

            if slot == 0 and assigned_count > 1:
                status = "completed"
            else:
                status = str(rng.choice(
                    config.ENROLLMENT_STATUSES,
                    p=[0.15, 0.15, 0.55, 0.10, 0.05],
                ))
            enrollment_rows.append({
                "enrollment_id": enrollment_id,
                "employee_id": employee_id,
                "course_id": course_id,
                "enrollment_date": enrollment_date,
                "status": status,
            })
            first_status = "waitlisted" if status == "waitlisted" else "enrolled"
            enrollment_event_rows.append({
                "event_id": f"EEV-{len(enrollment_event_rows) + 1:06d}",
                "enrollment_id": enrollment_id,
                "event_type": first_status,
                "event_date": enrollment_date,
                "status_after": first_status,
            })
            if status == "completed":
                force_pass = slot == 0 and assigned_count > 1
                score = round(float(rng.uniform(60, 100) if force_pass else rng.uniform(35, 100)), 2)
                passed = score >= 60
                completion_date = date.fromisoformat(enrollment_date) + timedelta(
                    days=int(rng.integers(0, 31))
                )
                completion_rows.append({
                    "completion_id": f"CMP-{config.PLANNING_YEAR}-{len(completion_rows) + 1:06d}",
                    "enrollment_id": enrollment_id,
                    "employee_id": employee_id,
                    "course_id": course_id,
                    "completion_date": completion_date.isoformat(),
                    "score": score,
                    "passed": passed,
                })
                event_date = completion_date
                if passed:
                    completed_courses.add(course_id)
                    completed_on[course_id] = completion_date
            elif status in {"in_progress", "dropped"}:
                event_date = date.fromisoformat(enrollment_date) + timedelta(
                    days=int(rng.integers(1, 31))
                )
            else:
                event_date = None
            if status not in {"enrolled", "waitlisted"}:
                enrollment_event_rows.append({
                    "event_id": f"EEV-{len(enrollment_event_rows) + 1:06d}",
                    "enrollment_id": enrollment_id,
                    "event_type": status,
                    "event_date": event_date.isoformat(),
                    "status_after": status,
                })

    return (
        pd.DataFrame(enrollment_rows, columns=[
            "enrollment_id", "employee_id", "course_id", "enrollment_date", "status",
        ]),
        pd.DataFrame(completion_rows, columns=[
            "completion_id", "enrollment_id", "employee_id", "course_id",
            "completion_date", "score", "passed",
        ]),
        pd.DataFrame(enrollment_event_rows, columns=[
            "event_id", "enrollment_id", "event_type", "event_date", "status_after",
        ]),
    )


def generate_reassessments(
    rng: np.random.Generator,
    employee_skills: pd.DataFrame,
    course_skills: pd.DataFrame,
    completions: pd.DataFrame,
) -> pd.DataFrame:
    """Append post-course proficiency events for a deterministic sample of passes."""
    if employee_skills.empty or course_skills.empty or completions.empty:
        return employee_skills
    latest = employee_skills.sort_values("assessed_date").drop_duplicates(
        ["employee_id", "skill_id"], keep="last"
    )
    proficiency = latest.set_index(["employee_id", "skill_id"])["current_proficiency"].to_dict()
    passed = completions[completions["passed"].astype(bool)]
    new_rows = []
    next_id = len(employee_skills) + 1
    for completion in passed.itertuples(index=False):
        if rng.random() >= 0.6:
            continue
        skills = course_skills.loc[
            course_skills["course_id"] == completion.course_id
        ]
        if skills.empty:
            continue
        skill = skills.iloc[int(rng.integers(0, len(skills)))]
        key = (completion.employee_id, skill["skill_id"])
        baseline = proficiency.get(key, 0)
        reassessed = min(5, max(baseline, int(skill["skill_level_gained"])))
        new_rows.append({
            "esk_id": f"ESK-{next_id:06d}",
            "employee_id": completion.employee_id,
            "skill_id": skill["skill_id"],
            "current_proficiency": reassessed,
            "assessed_date": (
                date.fromisoformat(completion.completion_date)
                + timedelta(days=int(rng.integers(1, 31)))
            ).isoformat(),
            "assessment_type": "post_course",
            "source_completion_id": completion.completion_id,
        })
        next_id += 1
    if not new_rows:
        return employee_skills
    return pd.concat([employee_skills, pd.DataFrame(new_rows)], ignore_index=True)


def generate_all_relationship_data(
    seed: int | None, master_data: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed if seed is not None else config.RANDOM_SEED)
    targets = generate_role_skill_targets(rng, master_data["roles"], master_data["skills"])
    employee_skills = generate_employee_skills(
        rng, master_data["employees"], master_data["skills"], targets
    )
    course_skills = generate_course_skills(rng, master_data["courses"], master_data["skills"])
    prerequisites = generate_prerequisites(rng, master_data["courses"])
    enrollments, completions, enrollment_events = generate_enrollments_and_completions(
        rng, master_data["employees"], master_data["courses"], prerequisites
    )
    employee_skills = generate_reassessments(
        rng, employee_skills, course_skills, completions
    )
    return {
        "role_skill_targets": targets,
        "employee_skills": employee_skills,
        "course_skills": course_skills,
        "prerequisites": prerequisites,
        "enrollments": enrollments,
        "enrollment_events": enrollment_events,
        "completions": completions,
    }
