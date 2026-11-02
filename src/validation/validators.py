"""Integrity and reconciliation checks for generated project data."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


PRIMARY_KEYS = {
    "employees": "employee_id",
    "roles": "role_id",
    "skills": "skill_id",
    "role_skill_targets": "rst_id",
    "employee_skills": "esk_id",
    "courses": "course_id",
    "course_skills": "csk_id",
    "prerequisites": "prq_id",
    "enrollments": "enrollment_id",
    "enrollment_events": "event_id",
    "completions": "completion_id",
    "budgets": "budget_id",
    "budget_events": "event_id",
}

FOREIGN_KEYS = {
    "employees": [("role_id", "roles", "role_id")],
    "budget_events": [
        ("budget_id", "budgets", "budget_id"),
        ("employee_id", "employees", "employee_id"),
        ("course_id", "courses", "course_id"),
    ],
    "role_skill_targets": [
        ("role_id", "roles", "role_id"),
        ("skill_id", "skills", "skill_id"),
    ],
    "employee_skills": [
        ("employee_id", "employees", "employee_id"),
        ("skill_id", "skills", "skill_id"),
    ],
    "course_skills": [
        ("course_id", "courses", "course_id"),
        ("skill_id", "skills", "skill_id"),
    ],
    "prerequisites": [
        ("course_id", "courses", "course_id"),
        ("prerequisite_course_id", "courses", "course_id"),
    ],
    "enrollments": [
        ("employee_id", "employees", "employee_id"),
        ("course_id", "courses", "course_id"),
    ],
    "enrollment_events": [("enrollment_id", "enrollments", "enrollment_id")],
    "completions": [
        ("enrollment_id", "enrollments", "enrollment_id"),
        ("employee_id", "employees", "employee_id"),
        ("course_id", "courses", "course_id"),
    ],
}

ID_PATTERNS = {
    "employees": re.compile(r"EMP-\d{6}"),
    "roles": re.compile(r"ROL-\d{6}"),
    "skills": re.compile(r"SKL-\d{6}"),
    "role_skill_targets": re.compile(r"RST-\d{6}"),
    "employee_skills": re.compile(r"ESK-\d{6}"),
    "courses": re.compile(r"CRS-\d{6}"),
    "course_skills": re.compile(r"CSK-\d{6}"),
    "prerequisites": re.compile(r"PRQ-\d{6}"),
    "enrollment_events": re.compile(r"EEV-\d{6}"),
    "completions": re.compile(r"CMP-\d{4}-\d{6}"),
    "budget_events": re.compile(r"BGE-\d{6}"),
}


def _check(
    name: str, ok: bool, detail: str = "", expected_exception: bool = False
) -> dict[str, Any]:
    status = "passed" if ok else ("warning" if expected_exception else "failed")
    return {"name": name, "status": status, "detail": detail}


def run_all_validations(data: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Validate keys, references, lifecycle, constraints, and budget arithmetic."""
    checks: list[dict[str, Any]] = []

    for table, key in PRIMARY_KEYS.items():
        if table not in data:
            continue
        frame = data[table]
        duplicates = int(frame[key].duplicated().sum())
        checks.append(_check(
            f"{table}.primary_key_unique",
            duplicates == 0,
            f"{duplicates} duplicate {key} value(s)",
        ))
        pattern = ID_PATTERNS.get(table)
        if pattern:
            invalid_ids = int((~frame[key].astype(str).str.fullmatch(pattern)).sum())
            checks.append(_check(
                f"{table}.id_format",
                invalid_ids == 0,
                f"{invalid_ids} ID(s) do not match {pattern.pattern}",
            ))

    for table, references in FOREIGN_KEYS.items():
        if table not in data:
            continue
        source = data[table]
        for field, parent_table, parent_key in references:
            missing = int((~source[field].isin(data[parent_table][parent_key])).sum())
            checks.append(_check(
                f"{table}.{field}_foreign_key",
                missing == 0,
                f"{missing} unresolved reference(s)",
            ))

    employee_skills = data["employee_skills"]
    completions = data["completions"]
    reassessments = employee_skills.dropna(subset=["source_completion_id"])
    missing_completions = int(
        (~reassessments["source_completion_id"].isin(completions["completion_id"])).sum()
    )
    checks.append(_check(
        "employee_skills.source_completion_id_foreign_key",
        missing_completions == 0,
        f"{missing_completions} unresolved completion reference(s)",
    ))
    allowed_values = {
        ("employees", "status"): {"active", "on_leave", "terminated"},
        ("courses", "status"): {"active", "inactive", "archived"},
        ("enrollments", "status"): {
            "enrolled", "in_progress", "completed", "dropped", "waitlisted",
        },
        ("enrollment_events", "event_type"): {
            "enrolled", "in_progress", "completed", "dropped", "waitlisted",
        },
        ("enrollment_events", "status_after"): {
            "enrolled", "in_progress", "completed", "dropped", "waitlisted",
        },
        ("employee_skills", "assessment_type"): {"baseline", "post_course"},
        ("role_skill_targets", "priority"): {"critical", "high", "medium", "low"},
    }
    for (table, field), allowed in allowed_values.items():
        if table not in data:
            continue
        invalid = int((~data[table][field].isin(allowed)).sum())
        checks.append(_check(
            f"{table}.{field}_enum",
            invalid == 0,
            f"{invalid} invalid value(s); expected {sorted(allowed)}",
        ))

    baseline_has_source = employee_skills.loc[
        employee_skills["assessment_type"] == "baseline", "source_completion_id"
    ].notna().any()
    reassessment_missing_source = employee_skills.loc[
        employee_skills["assessment_type"] == "post_course", "source_completion_id"
    ].isna().any()
    checks.append(_check(
        "employee_skills.assessment_source_traceable",
        not baseline_has_source and not reassessment_missing_source,
        "Baseline assessments have no completion source; post-course records reference one.",
    ))

    enrollments = data["enrollments"].set_index("enrollment_id")
    if not completions.empty:
        enrollment_dates = completions["enrollment_id"].map(enrollments["enrollment_date"])
        date_order = (
            pd.to_datetime(completions["completion_date"]) >= pd.to_datetime(enrollment_dates)
        )
        checks.append(_check(
            "completions.date_after_enrollment",
            bool(date_order.all()),
            f"{int((~date_order).sum())} completion date(s) precede enrollment",
        ))
        lifecycle_ok = completions["enrollment_id"].map(enrollments["status"]).eq("completed")
        checks.append(_check(
            "completions.enrollment_lifecycle",
            bool(lifecycle_ok.all()),
            f"{int((~lifecycle_ok).sum())} completion(s) have non-completed enrollment status",
        ))
    else:
        checks.append(_check("completions.date_after_enrollment", True))
        checks.append(_check("completions.enrollment_lifecycle", True))

    duplicate_rows = completions["enrollment_id"].duplicated(keep=False)
    duplicate_row_count = int(duplicate_rows.sum())
    ground_truth = data.get("ground_truth", pd.DataFrame())
    expected_duplicate_ids = set()
    if not ground_truth.empty:
        expected_duplicate_ids = set(ground_truth.loc[
            ground_truth["issue_type"] == "duplicate_completion", "entity_id"
        ])
    labelled_duplicates = set(completions.loc[duplicate_rows, "completion_id"]) & expected_duplicate_ids
    expected_duplicate_count = duplicate_row_count // 2
    duplicate_case_is_labelled = (
        duplicate_row_count > 0
        and len(labelled_duplicates) == expected_duplicate_count
    )
    checks.append(_check(
        "completions.one_event_per_enrollment",
        duplicate_row_count == 0,
        f"{duplicate_row_count} completion row(s) participate in duplicate events; "
        f"{len(labelled_duplicates)} duplicate event(s) are labelled ground truth",
        expected_exception=duplicate_case_is_labelled,
    ))

    if "enrollment_events" in data:
        events = data["enrollment_events"]
        if events.empty:
            checks.append(_check("enrollment_events.match_current_status", data["enrollments"].empty))
            checks.append(_check("enrollment_events.date_after_enrollment", True))
        else:
            latest_status = (
                events.sort_values(["event_date", "event_id"])
                .drop_duplicates("enrollment_id", keep="last")
                .set_index("enrollment_id")["status_after"]
            )
            current_status = data["enrollments"].set_index("enrollment_id")["status"]
            lifecycle_matches = current_status.eq(latest_status.reindex(current_status.index))
            checks.append(_check(
                "enrollment_events.match_current_status",
                bool(lifecycle_matches.all()),
                f"{int((~lifecycle_matches).sum())} enrollment snapshot(s) differ from event history",
            ))
            event_dates = events["enrollment_id"].map(enrollments["enrollment_date"])
            before_enrollment = (
                pd.to_datetime(events["event_date"]) < pd.to_datetime(event_dates)
            )
            checks.append(_check(
                "enrollment_events.date_after_enrollment",
                not bool(before_enrollment.any()),
                f"{int(before_enrollment.sum())} lifecycle event(s) predate enrollment",
            ))

    budgets = data["budgets"]
    reconciled = (
        (budgets["total_budget"] - budgets["spent"] - budgets["remaining"]).abs() <= 0.011
    )
    checks.append(_check(
        "budgets.total_spent_remaining_reconcile",
        bool(reconciled.all()),
        f"{int((~reconciled).sum())} budget row(s) do not reconcile",
    ))
    within_limit = (budgets["spent"] <= budgets["total_budget"]) & (budgets["spent"] >= 0)
    checks.append(_check(
        "budgets.within_limit",
        bool(within_limit.all()),
        f"{int((~within_limit).sum())} over/negative budget row(s)",
    ))
    if "budget_events" in data:
        event_spend = data["budget_events"].groupby("budget_id")["amount"].sum()
        reconciled_events = budgets.apply(
            lambda row: abs(
                float(row["spent"]) - float(event_spend.get(row["budget_id"], 0))
            ) <= 0.011,
            axis=1,
        )
        checks.append(_check(
            "budgets.spent_matches_budget_events",
            bool(reconciled_events.all()),
            f"{int((~reconciled_events).sum())} budget row(s) differ from event-ledger totals",
        ))
    if "learning_paths" in data:
        paths = data["learning_paths"]
        if paths.empty:
            path_spend = pd.Series(dtype=float)
        else:
            path_spend = (
                paths[["employee_id", "course_id"]]
                .drop_duplicates()
                .merge(data["employees"][["employee_id", "department"]], on="employee_id")
                .merge(data["courses"][["course_id", "cost"]], on="course_id")
                .groupby("department")["cost"]
                .sum()
            )
        expected_spend = budgets["department"].map(path_spend).fillna(0)
        spend_matches_paths = (expected_spend - budgets["spent"]).abs() <= 0.011
        checks.append(_check(
            "budgets.spent_matches_learning_paths",
            bool(spend_matches_paths.all()),
            f"{int((~spend_matches_paths).sum())} budget row(s) differ from selected path costs",
        ))

    target_duplicates = int(data["role_skill_targets"].duplicated(["role_id", "skill_id"]).sum())
    checks.append(_check(
        "role_skill_targets.unique_pair",
        target_duplicates == 0,
        f"{target_duplicates} duplicate role/skill pair(s)",
    ))
    course_skill_duplicates = int(data["course_skills"].duplicated(["course_id", "skill_id"]).sum())
    checks.append(_check(
        "course_skills.unique_pair",
        course_skill_duplicates == 0,
        f"{course_skill_duplicates} duplicate course/skill pair(s)",
    ))

    prerequisites = data["prerequisites"]
    if prerequisites.empty:
        checks.append(_check("prerequisites.acyclic_order", True))
    else:
        course_order = {
            course_id: index for index, course_id in enumerate(data["courses"]["course_id"])
        }
        acyclic = prerequisites.apply(
            lambda row: course_order[row["prerequisite_course_id"]]
            < course_order[row["course_id"]],
            axis=1,
        )
        checks.append(_check(
            "prerequisites.acyclic_order",
            bool(acyclic.all()),
            f"{int((~acyclic).sum())} prerequisite edge(s) do not point to an earlier course",
        ))

    if not data["enrollments"].empty and not prerequisites.empty:
        prerequisite_map = prerequisites.groupby("course_id")[
            "prerequisite_course_id"
        ].apply(set).to_dict()
        passed = completions[completions["passed"].astype(bool)]
        completion_dates = passed.groupby(["employee_id", "course_id"])["completion_date"].min().to_dict()
        violations = sum(
            1
            for enrollment in data["enrollments"].itertuples(index=False)
            for prerequisite in prerequisite_map.get(enrollment.course_id, set())
            if (enrollment.employee_id, prerequisite) not in completion_dates
            or pd.Timestamp(completion_dates[(enrollment.employee_id, prerequisite)])
            >= pd.Timestamp(enrollment.enrollment_date)
        )
        checks.append(_check(
            "enrollments.prerequisites_precede",
            violations == 0,
            f"{violations} enrollment(s) violate prerequisite completion order",
        ))
    else:
        checks.append(_check("enrollments.prerequisites_precede", True))

    recommendations = data.get("recommendations", pd.DataFrame())
    if not recommendations.empty:
        feasible = recommendations["recommendation_feasible"].astype(bool)
        conditions = (
            recommendations["meets_prerequisites"].astype(bool)
            & recommendations["within_budget"].astype(bool)
            & recommendations["available"].astype(bool)
            & recommendations["capacity_available"].astype(bool)
        )
        invalid = int((feasible & ~conditions).sum())
        checks.append(_check(
            "recommendations.feasible_constraints",
            invalid == 0,
            f"{invalid} feasible recommendation(s) fail a required constraint",
        ))

    summary = {
        "total": len(checks),
        "passed": sum(check["status"] == "passed" for check in checks),
        "failed": sum(check["status"] == "failed" for check in checks),
        "warnings": sum(check["status"] == "warning" for check in checks),
    }
    return {
        "passed": summary["failed"] == 0,
        "summary": summary,
        "checks": checks,
    }
