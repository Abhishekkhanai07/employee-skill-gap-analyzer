# Copilot prompt history

Tool: Copilot in VS Code  
Scope: This file records the user prompts used in this implementation session. AI responses are omitted, consistent with the submission FAQ.

## Prompt 1

> Business Context / Problem  
> Match employee skill gaps to courses, prerequisites, budgets and career pathways.
>
> Objective and Scope  
> Build a working solution for this end-to-end workflow: Match employee skill gaps to courses, prerequisites, budgets and career pathways. The solution should expose key decisions and exceptions, preserve traceability, and produce measurable outputs. Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics.
>
> Primary Actors / Systems  
> Employee/candidate, manager, HR partner, IT/operations partner and system administrator
>
> Business Workflow and Rules  
> 1. Generate/reference master data first: Employee, Role, Skill, RoleSkillTarget, EmployeeSkill.  
> 2. Generate dependent transaction/event records using valid parent IDs.  
> 3. Apply business logic: Define role skill targets and employee proficiency; map courses to skills and prerequisites; generate course duration/cost and availability; calculate gaps; recommend feasible learning paths; track enrollment, completion and proficiency reassessment.  
> 4. Persist state changes as explicit records/events where relevant; do not overwrite history.  
> 5. Generate outcomes and ground-truth labels from documented rules, not independent random assignment.
>
> Entities and Relationships  
> Core entities: Employee, Role, Skill, RoleSkillTarget, EmployeeSkill, Course, CourseSkill, Prerequisite, Enrollment, Completion, Budget. Define a primary key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for many-to-many relationships; retain event history for state changes; validate all joins. For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows.
>
> ID / Nomenclature Conventions  
> EMP-000001; SKL-000001; CRS-000001; ENR-<employee-id>-<course-id>; CMP-2026-000001; BUD-<department>-2026.
>
> Synthetic Data Generation Instructions (Granular)  
> Step 1 — Write a data dictionary for: Employee, Role, Skill, RoleSkillTarget, EmployeeSkill, Course, CourseSkill, Prerequisite, Enrollment, Completion, Budget. For each field specify type, required/optional, allowed values, units, uniqueness and validation rule.  
> Step 2 — Create parent/master tables first, then child and event tables. Apply this domain-specific generation logic: Define role skill targets and employee proficiency; map courses to skills and prerequisites; generate course duration/cost and availability; calculate gaps; recommend feasible learning paths; track enrollment, completion and proficiency reassessment.  
> Step 3 — Apply deterministic IDs and naming: EMP-000001; SKL-000001; CRS-000001; ENR-<employee-id>-<course-id>; CMP-2026-000001; BUD-<department>-2026. Keep counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files.  
> Step 4 — Generate the baseline volume: Generate 5,000 employees, 500 skills, 1,000 courses and 10,000 enrollments. Include course capacity, budget limits, prerequisite chains and completed courses. Use a fixed seed (e.g. 20261022) and parameterize scale so starter and full datasets use the same generator.  
> Step 5 — Generate valid baseline records first, then inject labelled edge cases: Recommendation violates prerequisite; budget exceeded; completion counted twice; skill gap remains after course without reassessment; course unavailable in planning period.  
> Step 6 — Calculate derived values (totals, balances, scores, statuses and dates) from source records rather than generating them independently.  
> Step 7 — Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features.  
> Step 8 — Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks.  
> Step 9 — Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.  
> Step 10 — Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility.
>
> Suggested Volume and Coverage  
> Generate 5,000 employees, 500 skills, 1,000 courses and 10,000 enrollments. Include course capacity, budget limits, prerequisite chains and completed courses.
>
> Required Edge Cases / Negative Scenarios  
> Recommendation violates prerequisite; budget exceeded; completion counted twice; skill gap remains after course without reassessment; course unavailable in planning period.
>
> Validation Rules / Acceptance Criteria  
> Recommendations close defined skill gaps; prerequisites and budgets are respected; learning outcomes are distinct from attendance/completion.
>
> Evaluation Focus for Generated Data  
> Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground truth; (g) fixed-seed reproducibility, documentation and lawful provenance.
>
> Public Data Guidance / Lawful Use  
> External data is optional. If used, record source URL, dataset/version, retrieval date, license/terms, attribution, transformations and fields discarded. Use only data you are legally permitted to access and redistribute; do not bypass access controls or collect confidential/personal information. If licensing or suitability is unclear, use synthetic data and cite public reference data only for schema inspiration.
>
> Before you submit, make sure you have  
> - Pushed your code to a public GitHub repository  
> - Added a README explaining how to run it  
> - Included any tests the problem asks for
>
> Candidate FAQ (PDF) and Submission Guidelines (PDF) were supplied in the project workspace.
>
> Can you compare the project with the PDFs and project description, fix gaps, and test it? If a database is needed, I can provide one.

## Prompt 2

> Can you please use this languages Layer / Technology: Frontend React + TypeScript; Backend Node.js + Express; Database PostgreSQL; Data generation Python; Testing Jest or Vitest; Charts Recharts.

## Prompt 3

> I have built an employee skill gap analysis and learning recommendation platform for the YottaFlex AI Round 3 coding challenge.
>
> Please review my entire existing project against the requirements below. First, inspect the codebase, database schema, data generator, API endpoints, frontend, tests, and README. Do not start rewriting the project or changing the UI before completing the review.
>
> ## Project objective
> Build a working end-to-end system that matches employee skill gaps to courses, prerequisites, budgets, and career pathways, while preserving traceability and producing measurable outputs.
>
> ## Required functionality
> 1. Master data: Employee, Role, Skill, RoleSkillTarget, EmployeeSkill.
> 2. Course management: Course, CourseSkill, Prerequisite, duration, cost, availability, and capacity.
> 3. Skill gap calculation based on required and current proficiency.
> 4. Course recommendations that respect prerequisites, budgets, availability, and capacity.
> 5. Enrollment, completion, and skill reassessment with explicit event history.
> 6. Career pathway recommendations.
> 7. Dashboard metrics and decision traceability.
> 8. Detection of all five required exception cases:
>    - Recommendation violates a prerequisite.
>    - Budget exceeded.
>    - Completion counted twice.
>    - Skill gap remains after course completion without reassessment.
>    - Course unavailable during the planning period.
>
> ## Synthetic data requirements
> Generate 5,000 employees, 500 skills, 1,000 courses, and 10,000 enrollments using a fixed seed of 20261022.
>
> Use deterministic IDs and valid foreign keys. Generate valid baseline records first, then inject clearly labelled anomalies. Calculate derived values from source records and maintain separate ground_truth.csv or ground_truth.json files.
>
> Verify primary-key uniqueness, foreign-key integrity, lifecycle transitions, arithmetic reconciliation, and reproducibility.
>
> ## What I need you to do
> 1. Compare the existing implementation against every requirement.
> 2. Identify which features are implemented, partially implemented, or missing.
> 3. Check whether dashboard metrics are calculated from actual generated data and backend results rather than hardcoded values.
> 4. Verify the five exception cases are detected correctly.
> 5. Run the existing tests, data validation, and production build. Fix any failures you discover.
> 6. Implement missing functionality using the existing architecture and technology stack.
> 7. Preserve working functionality and the current UI design. Avoid unnecessary refactoring or introducing new dependencies.
> 8. Update the README with setup instructions, generator commands, validation commands, architecture, business rules, assumptions, limitations, and verification results.
> 9. Ensure AI prompt history, data dictionary, schema, source manifest, and validation summary are included as required.
>
> Do not claim that a feature works unless you have verified it. Do not invent test results, and do not use fabricated metrics to make the application appear complete.
>
> After completing the review and fixes, provide a concise summary of what was correct, what changed, test/validation results, and remaining issues. Keep the project locally runnable and suitable for a public GitHub repository.

## AI-use note

Copilot was used to inspect the supplied project, implement the requested generator/API/UI changes, and run tests/builds. The candidate should review and understand the implementation and personally verify it before submission.
