"""Add explicitly labelled exception examples after valid baseline generation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import config


def _ground_truth_row(issue_type: str, entity_type: str, entity_id: str, **details: Any) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        **details,
    }


def inject_edge_cases(
    rng: np.random.Generator, data: dict[str, pd.DataFrame]
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Label available exception examples without changing baseline source facts.

    The completion-duplication case is represented by a second, immutable
    completion event; other cases are labelled rejected recommendation
    candidates, not valid learning-path recommendations.
    """
    ground_truth: list[dict[str, Any]] = []
    recommendations = data.get("recommendations", pd.DataFrame()).copy()

    def label_candidates(
        issue_type: str, mask: pd.Series, count: int, entity_type: str, expected: str
    ) -> None:
        matches = recommendations.loc[mask]
        for _, row in matches.head(count).iterrows():
            ground_truth.append(_ground_truth_row(
                issue_type,
                entity_type,
                f"{row['employee_id']}|{row['recommended_course_id']}|{row['skill_id']}",
                employee_id=row["employee_id"],
                course_id=row["recommended_course_id"],
                skill_id=row["skill_id"],
                expected_decision=expected,
            ))

    if not recommendations.empty:
        label_candidates(
            "prerequisite_violation",
            ~recommendations["meets_prerequisites"].astype(bool),
            config.EDGE_CASES["prerequisite_violation"],
            "recommendation_candidate",
            "reject_until_prerequisite_passed",
        )
        label_candidates(
            "budget_exceeded",
            ~recommendations["within_budget"].astype(bool),
            config.EDGE_CASES["budget_exceeded"],
            "recommendation_candidate",
            "reject_or_request_budget_approval",
        )
        label_candidates(
            "course_unavailable",
            ~recommendations["available"].astype(bool),
            config.EDGE_CASES["course_unavailable"],
            "recommendation_candidate",
            "reject_until_course_is_available",
        )

    # Duplicate events retain distinct completion IDs and point back to the
    # original enrollment, so the duplicate is explicit and auditable.
    completions = data["completions"]
    if not completions.empty:
        count = min(config.EDGE_CASES["duplicate_completion"], len(completions))
        duplicates = completions.head(count).copy()
        start = len(completions) + 1
        duplicates["completion_id"] = [
            f"CMP-{config.PLANNING_YEAR}-{index:06d}"
            for index in range(start, start + count)
        ]
        data["completions"] = pd.concat([completions, duplicates], ignore_index=True)
        for row in duplicates.itertuples(index=False):
            ground_truth.append(_ground_truth_row(
                "duplicate_completion",
                "completion",
                row.completion_id,
                enrollment_id=row.enrollment_id,
                expected_decision="count_enrollment_once",
            ))

    # A completion is a negative example if no later skill assessment exists.
    employee_skills = data["employee_skills"]
    course_skills = data["course_skills"]
    if not completions.empty and not employee_skills.empty:
        reassessments = employee_skills[
            employee_skills["assessment_type"] == "post_course"
        ]
        reassessed_completions = set(reassessments["source_completion_id"].dropna())
        for completion in completions.itertuples(index=False):
            if completion.completion_id not in reassessed_completions:
                ground_truth.append(_ground_truth_row(
                    "no_reassessment",
                    "completion",
                    completion.completion_id,
                    employee_id=completion.employee_id,
                    course_id=completion.course_id,
                    expected_decision="do_not_credit_skill_gain_without_reassessment",
                ))
                if sum(row["issue_type"] == "no_reassessment" for row in ground_truth) >= config.EDGE_CASES["no_reassessment"]:
                    break

    result = pd.DataFrame(ground_truth, columns=[
        "issue_type", "entity_type", "entity_id", "employee_id", "course_id",
        "skill_id", "enrollment_id", "expected_decision",
    ])
    return data, result
