#!/usr/bin/env python3
"""
YottaFlex Skill-Gap Analyzer — Main Entry Point
=================================================
Generates synthetic data for employee skill-gap analysis, course matching,
prerequisite validation, budget tracking and career pathway recommendations.

Usage:
    python main.py                    # Full generation with default seed
    python main.py --seed 20261022    # Explicit seed
    python main.py --starter          # Starter dataset (10% scale)
    python main.py --validate-only    # Re-validate existing output
    python main.py --reproduce        # Generate twice and compare checksums
"""

import argparse
import contextlib
import json
import os
import sys
import tempfile
import time

import pandas as pd

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import config


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="YottaFlex Skill-Gap Analyzer — Synthetic Data Generator"
    )
    parser.add_argument(
        "--seed", type=int, default=config.RANDOM_SEED,
        help=f"Random seed for reproducibility (default: {config.RANDOM_SEED})"
    )
    parser.add_argument(
        "--starter", action="store_true",
        help="Generate a starter dataset at 10%% scale"
    )
    parser.add_argument(
        "--output-dir", type=str, default=config.OUTPUT_DIR,
        help=f"Output directory (default: {config.OUTPUT_DIR})"
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Skip generation; validate existing output"
    )
    parser.add_argument(
        "--reproduce", action="store_true",
        help="Generate twice with same seed, compare checksums"
    )
    parser.add_argument(
        "--format", nargs="+", choices=["csv", "json", "sql"],
        default=["csv", "json", "sql"],
        help="Output formats (default: csv json sql)"
    )
    return parser.parse_args()


def apply_scale(scale: float):
    """Scale volume parameters for starter/full datasets."""
    config.NUM_EMPLOYEES = max(10, int(config.NUM_EMPLOYEES * scale))
    config.NUM_SKILLS = max(10, int(config.NUM_SKILLS * scale))
    config.NUM_COURSES = max(10, int(config.NUM_COURSES * scale))
    config.NUM_ENROLLMENTS = max(10, int(config.NUM_ENROLLMENTS * scale))
    config.NUM_ROLES = max(5, int(config.NUM_ROLES * scale))
    for key in config.EDGE_CASES:
        config.EDGE_CASES[key] = max(1, int(config.EDGE_CASES[key] * scale))


def run_generation(seed: int, output_dir: str, formats: list):
    """Execute the full generation pipeline."""
    from src.generators.master_data import generate_all_master_data
    from src.generators.relationship_data import generate_all_relationship_data
    from src.generators.edge_cases import inject_edge_cases
    from src.logic.gap_analysis import (
        calculate_skill_gaps,
        recommend_courses,
        generate_learning_paths,
    )
    from src.logic.learning_paths import (
        analyze_career_pathways,
        generate_outcome_summary,
    )
    from src.validation.validators import run_all_validations
    from src.export.exporter import export_all

    import numpy as np

    print("=" * 70)
    print("  YottaFlex Skill-Gap Analyzer — Data Generation Pipeline")
    print("=" * 70)
    print(f"  Seed          : {seed}")
    print(f"  Employees     : {config.NUM_EMPLOYEES:,}")
    print(f"  Skills        : {config.NUM_SKILLS:,}")
    print(f"  Courses       : {config.NUM_COURSES:,}")
    print(f"  Enrollments   : {config.NUM_ENROLLMENTS:,}")
    print(f"  Roles         : {config.NUM_ROLES:,}")
    print(f"  Output Dir    : {output_dir}")
    print(f"  Formats       : {', '.join(formats)}")
    print("=" * 70)

    # ── Step 1: Generate master/parent data ───────────────────────────
    print("\n[1/8] Generating master data (Employee, Role, Skill, Course, Budget)...")
    t0 = time.time()
    master_data = generate_all_master_data(seed=seed)
    print(f"       Done in {time.time()-t0:.1f}s")
    for name, df in master_data.items():
        print(f"       {name:20s}: {len(df):>7,} rows")

    # ── Step 2: Generate relationship/transaction data ────────────────
    print("\n[2/8] Generating relationship & transaction data...")
    t0 = time.time()
    rel_data = generate_all_relationship_data(seed=seed, master_data=master_data)
    print(f"       Done in {time.time()-t0:.1f}s")
    for name, df in rel_data.items():
        print(f"       {name:20s}: {len(df):>7,} rows")

    # Combine all data
    all_data = {**master_data, **rel_data}

    # ── Step 3: Business logic — Skill gaps ───────────────────────────
    print("\n[3/8] Calculating skill gaps...")
    t0 = time.time()
    skill_gaps = calculate_skill_gaps(
        all_data["employees"],
        all_data["role_skill_targets"],
        all_data["employee_skills"],
    )
    all_data["skill_gaps"] = skill_gaps
    print(f"       Done in {time.time()-t0:.1f}s — {len(skill_gaps):,} gap records")
    gaps_nonzero = skill_gaps[skill_gaps["gap"] > 0]
    print(f"       Non-zero gaps: {len(gaps_nonzero):,}")

    # ── Step 4: Recommendations ───────────────────────────────────────
    print("\n[4/8] Generating course recommendations...")
    t0 = time.time()
    recommendations = recommend_courses(
        skill_gaps, all_data["course_skills"], all_data["courses"],
        all_data["prerequisites"], all_data["completions"],
        all_data["budgets"], all_data["employees"], all_data["enrollments"],
    )
    all_data["recommendations"] = recommendations
    print(f"       Done in {time.time()-t0:.1f}s — {len(recommendations):,} recommendations")

    # ── Step 5: Learning paths & career pathways ──────────────────────
    print("\n[5/8] Building learning paths & career pathways...")
    t0 = time.time()
    learning_paths = generate_learning_paths(
        recommendations, all_data["prerequisites"], all_data["courses"],
    )
    all_data["learning_paths"] = learning_paths
    budget_events = pd.DataFrame(columns=[
        "event_id", "budget_id", "employee_id", "course_id",
        "event_type", "event_date", "amount",
    ])
    if not learning_paths.empty:
        planned_courses = (
            learning_paths[["employee_id", "course_id", "estimated_start"]]
            .drop_duplicates(["employee_id", "course_id"])
            .merge(all_data["employees"][["employee_id", "department"]], on="employee_id")
            .merge(all_data["courses"][["course_id", "cost"]], on="course_id")
        )
        planned_courses["budget_id"] = planned_courses["department"].map(
            lambda department: f"BUD-{department}-{config.PLANNING_YEAR}"
        )
        budget_events = planned_courses.rename(columns={
            "estimated_start": "event_date",
            "cost": "amount",
        })
        budget_events.insert(
            0, "event_id",
            [f"BGE-{index:06d}" for index in range(1, len(budget_events) + 1)],
        )
        budget_events["event_type"] = "path_planned"
        budget_events = budget_events[[
            "event_id", "budget_id", "employee_id", "course_id",
            "event_type", "event_date", "amount",
        ]]
        path_spend = budget_events.merge(
            all_data["budgets"][["budget_id", "department"]], on="budget_id"
        ).groupby("department")["amount"].sum()
        all_data["budgets"]["spent"] = (
            all_data["budgets"]["department"].map(path_spend).fillna(0).round(2)
        )
        all_data["budgets"]["remaining"] = (
            all_data["budgets"]["total_budget"] - all_data["budgets"]["spent"]
        ).round(2)
    all_data["budget_events"] = budget_events

    career_pathways = analyze_career_pathways(
        all_data["employees"], all_data["roles"],
        skill_gaps, learning_paths,
    )
    all_data["career_pathways"] = career_pathways
    print(f"       Done in {time.time()-t0:.1f}s")
    print(f"       Learning paths : {len(learning_paths):,} steps")
    print(f"       Career pathways: {len(career_pathways):,} employees")

    # ── Step 6: Inject edge cases ─────────────────────────────────────
    print("\n[6/8] Injecting labelled edge cases / anomalies...")
    t0 = time.time()
    rng = np.random.default_rng(seed)
    all_data, ground_truth = inject_edge_cases(rng, all_data)
    all_data["ground_truth"] = ground_truth
    print(f"       Done in {time.time()-t0:.1f}s — {len(ground_truth):,} anomalies injected")
    for itype in ground_truth["issue_type"].value_counts().items():
        print(f"         {itype[0]:30s}: {itype[1]}")

    # ── Step 7: Validation ────────────────────────────────────────────
    print("\n[7/8] Running validation suite...")
    t0 = time.time()
    validation_results = run_all_validations(all_data)
    print(f"       Done in {time.time()-t0:.1f}s")
    summary = validation_results["summary"]
    print(f"       Total checks : {summary['total']}")
    print(f"       Passed       : {summary['passed']}")
    print(f"       Failed       : {summary['failed']}")
    print(f"       Warnings     : {summary['warnings']}")

    # ── Step 8: Generate outcomes & export ────────────────────────────
    print("\n[8/8] Generating outcome summary & exporting data...")
    t0 = time.time()
    outcomes = generate_outcome_summary(
        skill_gaps, recommendations, learning_paths,
        career_pathways, all_data["enrollments"], all_data["completions"],
        all_data["budgets"],
        employee_skills_df=all_data["employee_skills"],
    )

    export_results = export_all(
        data=all_data,
        ground_truth_df=ground_truth,
        validation_summary=validation_results,
        outcomes=outcomes,
        output_dir=output_dir,
        seed=seed,
        formats=formats,
    )
    print(f"       Done in {time.time()-t0:.1f}s")
    print(f"       Files written: {len(export_results)}")

    print("\n" + "=" * 70)
    print("  GENERATION COMPLETE")
    print("=" * 70)

    return all_data, validation_results


def run_reproducibility_check(seed: int, output_dir: str):
    """Run the full pipeline twice and compare all exported data checksums."""

    print("\n" + "=" * 70)
    print("  REPRODUCIBILITY CHECK")
    print("=" * 70)
    print(f"  Seed: {seed}")
    os.makedirs(output_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="yottaflex-repro-") as temp_dir:
        manifests = []
        with open(os.devnull, "w", encoding="utf-8") as sink:
            with contextlib.redirect_stdout(sink):
                for run_number in (1, 2):
                    run_dir = os.path.join(temp_dir, f"run{run_number}")
                    run_generation(seed, run_dir, ["csv", "json", "sql"])
                    with open(
                        os.path.join(run_dir, "source_manifest.json"),
                        encoding="utf-8",
                    ) as manifest_file:
                        manifests.append(json.load(manifest_file))

    first, second = manifests
    row_counts_match = first["row_counts"] == second["row_counts"]
    checksums_match = (
        first["generated_files_sha256"] == second["generated_files_sha256"]
    )
    all_match = row_counts_match and checksums_match
    report = {
        "seed": seed,
        "all_match": all_match,
        "row_counts_match": row_counts_match,
        "checksums_match": checksums_match,
        "row_counts": first["row_counts"],
        "ground_truth_rows": first["ground_truth_rows"],
        "generated_files_sha256": first["generated_files_sha256"],
    }
    report_path = os.path.join(output_dir, "reproducibility_report.json")
    with open(report_path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, sort_keys=True)
        report_file.write("\n")

    print(f"  Generated file checksums: {len(first['generated_files_sha256'])}")
    print(f"  Row counts match       : {row_counts_match}")
    print(f"  Checksums match        : {checksums_match}")
    print(f"  Overall: {'ALL OUTPUTS MATCH' if all_match else 'MISMATCH DETECTED'}")
    print(f"  Report saved to: {report_path}")
    return all_match


def main():
    """Main entry point."""
    args = parse_args()

    # Apply scale
    if args.starter:
        apply_scale(0.10)
        print("Using STARTER scale (10%)")

    if args.reproduce:
        success = run_reproducibility_check(args.seed, args.output_dir)
        sys.exit(0 if success else 1)

    if args.validate_only:
        import pandas as pd
        from src.validation.validators import run_all_validations

        required_tables = [
            "roles", "skills", "employees", "courses", "budgets",
            "role_skill_targets", "employee_skills", "course_skills",
            "prerequisites", "enrollments", "enrollment_events",
            "completions", "budget_events", "skill_gaps",
            "recommendations", "learning_paths", "career_pathways",
        ]
        data = {}
        for table in required_tables:
            path = os.path.join(args.output_dir, f"{table}.csv")
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Cannot validate; missing generated table: {path}")
            data[table] = pd.read_csv(path)
        ground_truth_path = os.path.join(args.output_dir, "ground_truth.csv")
        if os.path.isfile(ground_truth_path):
            data["ground_truth"] = pd.read_csv(ground_truth_path)
        validation = run_all_validations(data)
        print(json.dumps(validation, indent=2))
        sys.exit(0 if validation["passed"] else 1)

    all_data, validation = run_generation(args.seed, args.output_dir, args.format)

    # Exit with non-zero if validation failed
    if not validation.get("passed", True):
        print("\n⚠ Some validation checks failed. Review validation_summary.json")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
