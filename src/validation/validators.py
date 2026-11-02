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
    "skill_gaps": [
        ("employee_id", "employees", "employee_id"),
        ("role_id", "roles", "role_id"),
        ("skill_id", "skills", "skill_id"),
    ],
    "recommendations": [
        ("employee_id", "employees", "employee_id"),
        ("skill_id", "skills", "skill_id"),
        ("recommended_course_id", "courses", "course_id"),
    ],
    "learning_paths": [
        ("employee_id", "employees", "employee_id"),
        ("course_id", "courses", "course_id"),
        ("skill_id", "skills", "skill_id"),
    ],
    "career_pathways": [("employee_id", "employees", "employee_id")],
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

ALLOWED_ENROLLMENT_TRANSITIONS = {
    "enrolled": {"in_progress", "completed", "dropped"},
    "in_progress": {"completed", "dropped"},
    "waitlisted": {"enrolled", "dropped"},
    "completed": set(),
    "dropped": set(),
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

    budgets = data["budgets"]
    expected_budget_ids = (
        "BUD-" + budgets["department"].astype(str) + "-" + budgets["year"].astype(str)
    )
    checks.append(_check(
        "budgets.id_format",
        bool(budgets["budget_id"].astype(str).eq(expected_budget_ids).all()),
        f"{int((~budgets['budget_id'].astype(str).eq(expected_budget_ids)).sum())} budget ID(s) do not match department/year",
    ))
    enrollments_for_ids = data["enrollments"]
    expected_enrollment_ids = (
        "ENR-" + enrollments_for_ids["employee_id"].astype(str)
        + "-" + enrollments_for_ids["course_id"].astype(str)
    )
    checks.append(_check(
        "enrollments.id_matches_employee_course",
        bool(enrollments_for_ids["enrollment_id"].astype(str).eq(expected_enrollment_ids).all()),
        f"{int((~enrollments_for_ids['enrollment_id'].astype(str).eq(expected_enrollment_ids)).sum())} enrollment ID(s) mismatch their references",
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
    post_course_skills = employee_skills[
        employee_skills["assessment_type"] == "post_course"
    ]
    if not post_course_skills.empty:
        linked_assessments = post_course_skills.merge(
            completions[[
                "completion_id", "employee_id", "completion_date", "passed",
            ]],
            left_on="source_completion_id",
            right_on="completion_id",
            suffixes=("_assessment", "_completion"),
        )
        assessment_link_ok = (
            linked_assessments["employee_id_assessment"].eq(
                linked_assessments["employee_id_completion"]
            )
            & linked_assessments["passed"].astype(bool)
            & (
                pd.to_datetime(linked_assessments["assessed_date"])
                > pd.to_datetime(linked_assessments["completion_date"])
            )
        )
        invalid_assessment_links = int((~assessment_link_ok).sum()) + (
            len(post_course_skills) - len(linked_assessments)
        )
    else:
        invalid_assessment_links = 0
    checks.append(_check(
        "employee_skills.post_course_links_valid_passed_completion",
        invalid_assessment_links == 0,
        f"{invalid_assessment_links} post-course assessment(s) lack a later passed completion for the same employee",
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
        enrollment_facts = data["enrollments"][[
            "enrollment_id", "employee_id", "course_id",
        ]]
        linked_completions = completions.merge(
            enrollment_facts,
            on="enrollment_id",
            suffixes=("_completion", "_enrollment"),
        )
        completion_join_ok = (
            linked_completions["employee_id_completion"].eq(
                linked_completions["employee_id_enrollment"]
            )
            & linked_completions["course_id_completion"].eq(
                linked_completions["course_id_enrollment"]
            )
        )
        invalid_completion_joins = int((~completion_join_ok).sum()) + (
            len(completions) - len(linked_completions)
        )
        checks.append(_check(
            "completions.match_enrollment_employee_course",
            invalid_completion_joins == 0,
            f"{invalid_completion_joins} completion(s) do not match their enrollment",
        ))
    else:
        checks.append(_check("completions.date_after_enrollment", True))
        checks.append(_check("completions.enrollment_lifecycle", True))
        checks.append(_check("completions.match_enrollment_employee_course", True))

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
            ordered_events = events.sort_values(["enrollment_id", "event_date", "event_id"])
            invalid_transitions = 0
            for _, history in ordered_events.groupby("enrollment_id", sort=False):
                previous_status = None
                for event in history.itertuples(index=False):
                    if event.event_type != event.status_after:
                        invalid_transitions += 1
                    if previous_status is None:
                        if event.status_after not in {"enrolled", "waitlisted"}:
                            invalid_transitions += 1
                    elif event.status_after not in ALLOWED_ENROLLMENT_TRANSITIONS.get(
                        previous_status, set()
                    ):
                        invalid_transitions += 1
                    previous_status = event.status_after
            checks.append(_check(
                "enrollment_events.valid_state_transitions",
                invalid_transitions == 0,
                f"{invalid_transitions} invalid lifecycle transition(s)",
            ))
        if events.empty:
            checks.append(_check("enrollment_events.valid_state_transitions", True))

    enrollment_counts = data["enrollments"]["course_id"].value_counts()
    capacity = data["courses"].set_index("course_id")["capacity"]
    exceeded_courses = int((enrollment_counts > capacity.reindex(enrollment_counts.index)).sum())
    checks.append(_check(
        "enrollments.course_capacity",
        exceeded_courses == 0,
        f"{exceeded_courses} course(s) exceed enrollment capacity",
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
    if "skill_gaps" in data and not data["skill_gaps"].empty:
        expected_gaps = (
            data["skill_gaps"]["target_proficiency"]
            - data["skill_gaps"]["current_proficiency"]
        ).clip(lower=0)
        arithmetic_ok = data["skill_gaps"]["gap"].eq(expected_gaps)
        checks.append(_check(
            "skill_gaps.proficiency_arithmetic",
            bool(arithmetic_ok.all()),
            f"{int((~arithmetic_ok).sum())} skill gap(s) do not equal max(target-current, 0)",
        ))
    elif "skill_gaps" in data:
        checks.append(_check("skill_gaps.proficiency_arithmetic", True))
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
        duplicate_candidates = int(recommendations.duplicated(
            ["employee_id", "skill_id", "recommended_course_id"]
        ).sum())
        checks.append(_check(
            "recommendations.employee_skill_course_unique",
            duplicate_candidates == 0,
            f"{duplicate_candidates} duplicate recommendation candidate(s)",
        ))

    for table, keys, check_name in [
        ("skill_gaps", ["employee_id", "skill_id"], "skill_gaps.employee_skill_unique"),
        ("learning_paths", ["employee_id", "path_step"], "learning_paths.employee_step_unique"),
        ("career_pathways", ["employee_id"], "career_pathways.employee_unique"),
    ]:
        if table in data:
            duplicates = int(data[table].duplicated(keys).sum())
            checks.append(_check(
                check_name,
                duplicates == 0,
                f"{duplicates} duplicate row(s) for key {keys}",
            ))

    if "ground_truth" in data:
        expected_decisions = {
            "prerequisite_violation": "reject_until_prerequisite_passed",
            "budget_exceeded": "reject_or_request_budget_approval",
            "duplicate_completion": "count_enrollment_once",
            "no_reassessment": "do_not_credit_skill_gain_without_reassessment",
            "course_unavailable": "reject_until_course_is_available",
        }
        truth = data["ground_truth"]
        present_cases = set(truth["issue_type"])
        missing_cases = set(expected_decisions) - present_cases
        valid_labels = truth.apply(
            lambda row: expected_decisions.get(row["issue_type"]) == row["expected_decision"],
            axis=1,
        )

        candidate_truth = truth[truth["issue_type"].isin({
            "prerequisite_violation", "budget_exceeded", "course_unavailable",
        })]
        recommendation_ids = set()
        recommendation_conditions: dict[str, dict[str, bool]] = {}
        if not recommendations.empty:
            identified_recommendations = recommendations.assign(
                entity_id=(
                    recommendations["employee_id"].astype(str)
                    + "|"
                    + recommendations["recommended_course_id"].astype(str)
                    + "|"
                    + recommendations["skill_id"].astype(str)
                )
            )
            recommendation_ids = set(identified_recommendations["entity_id"])
            recommendation_conditions = {
                issue_type: identified_recommendations.set_index("entity_id")[column].astype(bool).to_dict()
                for issue_type, column in {
                    "prerequisite_violation": "meets_prerequisites",
                    "budget_exceeded": "within_budget",
                    "course_unavailable": "available",
                }.items()
            }
        candidate_ids_valid = candidate_truth["entity_id"].isin(recommendation_ids)
        candidate_conditions_valid = candidate_truth.apply(
            lambda row: not recommendation_conditions.get(row["issue_type"], {}).get(
                row["entity_id"], True
            ),
            axis=1,
        )

        completion_ids = set(completions["completion_id"])
        duplicate_enrollments = set(completions.loc[
            completions["enrollment_id"].duplicated(keep=False), "enrollment_id"
        ])
        duplicate_truth = truth[truth["issue_type"] == "duplicate_completion"]
        duplicate_labels_valid = duplicate_truth["entity_id"].isin(completion_ids) & duplicate_truth[
            "enrollment_id"
        ].isin(duplicate_enrollments)

        reassessment_truth = truth[truth["issue_type"] == "no_reassessment"]
        completion_by_id = completions.set_index("completion_id").to_dict("index")
        role_by_employee = data["employees"].set_index("employee_id")["role_id"].to_dict()
        target_by_role_skill = data["role_skill_targets"].set_index(
            ["role_id", "skill_id"]
        )["target_proficiency"].to_dict()
        baseline = employee_skills[
            employee_skills["assessment_type"] == "baseline"
        ].copy()
        if not baseline.empty:
            baseline["assessed_date"] = pd.to_datetime(baseline["assessed_date"])
            baseline = baseline.sort_values("assessed_date").drop_duplicates(
                ["employee_id", "skill_id"], keep="last"
            )
        baseline_proficiency = baseline.set_index(
            ["employee_id", "skill_id"]
        )["current_proficiency"].to_dict()
        latest_assessment = employee_skills.assign(
            assessed_date=pd.to_datetime(employee_skills["assessed_date"])
        ).groupby(["employee_id", "skill_id"])["assessed_date"].max().to_dict()
        course_skill_pairs = set(zip(
            data["course_skills"]["course_id"], data["course_skills"]["skill_id"]
        ))
        reassessment_results = []
        for label in reassessment_truth.itertuples(index=False):
            completion = completion_by_id.get(label.entity_id)
            if completion is None:
                reassessment_results.append(False)
                continue
            employee_id = completion["employee_id"]
            course_id = completion["course_id"]
            skill_id = label.skill_id
            target = target_by_role_skill.get(
                (role_by_employee.get(employee_id), skill_id)
            )
            current = baseline_proficiency.get((employee_id, skill_id), 0)
            assessed_after = latest_assessment.get((employee_id, skill_id))
            reassessment_results.append(
                bool(completion["passed"])
                and skill_id is not None
                and (course_id, skill_id) in course_skill_pairs
                and target is not None
                and current < target
                and label.current_proficiency == current
                and label.target_proficiency == target
                and (
                    assessed_after is None
                    or pd.Timestamp(assessed_after) <= pd.Timestamp(completion["completion_date"])
                )
            )
        reassessment_labels_valid = pd.Series(
            reassessment_results, index=reassessment_truth.index, dtype=bool
        )
        exception_labels_valid = (
            not missing_cases
            and bool(valid_labels.all())
            and bool(candidate_ids_valid.all())
            and bool(candidate_conditions_valid.all())
            and bool(duplicate_labels_valid.all())
            and bool(reassessment_labels_valid.all())
        )
        checks.append(_check(
            "ground_truth.required_exceptions_match_source_records",
            exception_labels_valid,
            f"Missing issue types: {sorted(missing_cases)}; "
            f"{int((~valid_labels).sum())} invalid decisions; "
            f"{int((~candidate_ids_valid).sum())} unmatched candidates; "
            f"{int((~candidate_conditions_valid).sum())} candidates without the labelled exception; "
            f"{int((~duplicate_labels_valid).sum())} invalid duplicate labels; "
            f"{int((~reassessment_labels_valid).sum())} invalid remaining-gap/no-reassessment labels",
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
