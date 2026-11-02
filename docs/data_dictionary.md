# Data Dictionary — YottaFlex Skill-Gap Analyzer

## Overview

This document defines every entity, field, relationship, and validation rule
in the YottaFlex Skill-Gap Analyzer system.

**Proficiency Scale:** 1 = Awareness, 2 = Beginner, 3 = Intermediate, 4 = Advanced, 5 = Expert

---

## Entity–Relationship Summary

```
Employee ──N:1──▶ Role
    │                │
    │ 1:N            │ 1:N
    ▼                ▼
EmployeeSkill    RoleSkillTarget
    │                │
    │ N:1            │ N:1
    ▼                ▼
  Skill ◀───N:1─── CourseSkill ──N:1──▶ Course
                                          │
                                     1:N  │  1:N
                                          ▼
                                    Prerequisite
                                          │
                  Enrollment ◀──────────  │
                    │  │                  │
                    │  └──▶ Course ◀──────┘
                    ▼
                Completion

Budget  (per department per year)
```

### Cardinality Table

| Relationship                        | Cardinality | Required | Notes                          |
|-------------------------------------|-------------|----------|--------------------------------|
| Employee → Role                     | N:1         | Yes      | FK: employee.role_id           |
| Employee → EmployeeSkill            | 1:N         | No       | Via employee_id                |
| Role → RoleSkillTarget              | 1:N         | No       | Via role_id                    |
| Skill → RoleSkillTarget             | 1:N         | No       | Via skill_id                   |
| Skill → EmployeeSkill               | 1:N         | No       | Via skill_id                   |
| Skill → CourseSkill                  | 1:N         | No       | Via skill_id                   |
| Course → CourseSkill (bridge)        | 1:N         | No       | N:M between Course and Skill   |
| Course → Prerequisite               | 1:N         | No       | course_id is the dependent     |
| Course → Enrollment                 | 1:N         | No       | Via course_id                  |
| Employee → Enrollment               | 1:N         | No       | Via employee_id                |
| Enrollment → Completion             | 1:0..N      | No       | Duplicates appear only as labelled anomalies |
| Budget → Department                 | 1:1         | Yes      | Logical link via dept name     |
| Enrollment → EnrollmentEvent        | 1:N         | Yes      | Append-only lifecycle history  |
| Budget → BudgetEvent                | 1:N         | No       | Source events for planned spend |
| Completion → EmployeeSkill          | 1:0..N      | No       | Optional linked reassessment   |

---

## Entities

### 1. Employee

| Field        | Type   | Required | Unique | Allowed Values                          | Validation                |
|--------------|--------|----------|--------|-----------------------------------------|---------------------------|
| employee_id  | str    | Yes      | Yes    | `EMP-{06d}`                             | Immutable PK              |
| first_name   | str    | Yes      | No     | —                                       | Non-empty                 |
| last_name    | str    | Yes      | No     | —                                       | Non-empty                 |
| email        | str    | Yes      | Yes    | Valid synthetic email                   | `first.last@example.test` (reserved test domain) |
| department   | str    | Yes      | No     | config.DEPARTMENTS (12 values)          | Must match role's dept    |
| role_id      | str    | Yes      | No     | FK → Role.role_id                       | Must exist in Role        |
| hire_date    | date   | Yes      | No     | 2015-01-01 to 2026-06-30               | ≤ today                   |
| status       | str    | Yes      | No     | active, on_leave, terminated            | Enum                      |

### 2. Role

| Field       | Type | Required | Unique | Allowed Values                                          |
|-------------|------|----------|--------|---------------------------------------------------------|
| role_id     | str  | Yes      | Yes    | `ROL-{06d}`                                             |
| role_name   | str  | Yes      | Yes    | —                                                       |
| department  | str  | Yes      | No     | config.DEPARTMENTS                                      |
| level       | str  | Yes      | No     | junior, mid, senior, lead, principal, director          |
| description | str  | No       | No     | —                                                       |

### 3. Skill

| Field       | Type | Required | Unique | Allowed Values          |
|-------------|------|----------|--------|-------------------------|
| skill_id    | str  | Yes      | Yes    | `SKL-{06d}`             |
| skill_name  | str  | Yes      | Yes    | —                       |
| category    | str  | Yes      | No     | config.SKILL_CATEGORIES |
| description | str  | No       | No     | —                       |

### 4. RoleSkillTarget

| Field              | Type | Required | Unique | Allowed Values               |
|--------------------|------|----------|--------|------------------------------|
| rst_id             | str  | Yes      | Yes    | `RST-{06d}`                  |
| role_id            | str  | Yes      | No     | FK → Role.role_id            |
| skill_id           | str  | Yes      | No     | FK → Skill.skill_id          |
| target_proficiency | int  | Yes      | No     | 1–5                          |
| priority           | str  | Yes      | No     | critical, high, medium, low  |

**Constraint:** UNIQUE(role_id, skill_id)

### 5. EmployeeSkill

| Field               | Type | Required | Unique | Allowed Values                    |
|---------------------|------|----------|--------|-----------------------------------|
| esk_id              | str  | Yes      | Yes    | `ESK-{06d}`                       |
| employee_id         | str  | Yes      | No     | FK → Employee.employee_id         |
| skill_id            | str  | Yes      | No     | FK → Skill.skill_id              |
| current_proficiency | int  | Yes      | No     | 1–5                               |
| assessed_date       | date | Yes      | No     | Baseline: 2024–2025; reassessment: after a linked completion |
| assessment_type     | str  | Yes      | No     | `baseline`, `post_course`          |
| source_completion_id| str  | No       | No     | FK → Completion.completion_id; required for `post_course` |

**Note:** Event-sourced. Multiple assessments per (employee, skill) are permitted; the latest by date is the current proficiency. Post-course records retain the passed completion event that triggered reassessment, and their assessment date must be later than completion.

### 6. Course

| Field              | Type  | Required | Unique | Allowed Values              | Unit  |
|--------------------|-------|----------|--------|-----------------------------|-------|
| course_id          | str   | Yes      | Yes    | `CRS-{06d}`                 |       |
| course_name        | str   | Yes      | No     | —                           |       |
| provider           | str   | Yes      | No     | ~20 providers               |       |
| duration_hours     | int   | Yes      | No     | 4–120                       | hours |
| cost               | float | Yes      | No     | 50–5000                     | USD   |
| capacity           | int   | Yes      | No     | 20–200                      |       |
| availability_start | date  | Yes      | No     | Within 2026                 |       |
| availability_end   | date  | Yes      | No     | 30–180 days after start; can extend into 2027 |       |
| status             | str   | Yes      | No     | active, inactive, archived  |       |

### 7. CourseSkill (Bridge Table)

| Field              | Type | Required | Unique | Allowed Values        |
|--------------------|------|----------|--------|-----------------------|
| csk_id             | str  | Yes      | Yes    | `CSK-{06d}`           |
| course_id          | str  | Yes      | No     | FK → Course.course_id |
| skill_id           | str  | Yes      | No     | FK → Skill.skill_id   |
| skill_level_gained | int  | Yes      | No     | 1–5                   |

**Constraint:** UNIQUE(course_id, skill_id)

### 8. Prerequisite

| Field                   | Type | Required | Unique | Allowed Values        |
|-------------------------|------|----------|--------|-----------------------|
| prq_id                  | str  | Yes      | Yes    | `PRQ-{06d}`           |
| course_id               | str  | Yes      | No     | FK → Course.course_id |
| prerequisite_course_id  | str  | Yes      | No     | FK → Course.course_id |

**Constraints:**
- UNIQUE(course_id, prerequisite_course_id)
- course_id ≠ prerequisite_course_id
- No circular prerequisite chains
- Max chain depth: 3

### 9. Enrollment

| Field           | Type | Required | Unique | Allowed Values                                            |
|-----------------|------|----------|--------|-----------------------------------------------------------|
| enrollment_id   | str  | Yes      | Yes    | `ENR-{emp_id}-{crs_id}`                                  |
| employee_id     | str  | Yes      | No     | FK → Employee.employee_id                                 |
| course_id       | str  | Yes      | No     | FK → Course.course_id                                     |
| enrollment_date | date | Yes      | No     | Within enrollment range                                   |
| status          | str  | Yes      | No     | enrolled, in_progress, completed, dropped, waitlisted     |

`enrollment_id` is deterministic and unique per employee/course. Each state transition is retained in `EnrollmentEvent`; `status` is the current snapshot derived from the latest event.

### 10. Completion

| Field           | Type  | Required | Unique | Allowed Values                    |
|-----------------|-------|----------|--------|-----------------------------------|
| completion_id   | str   | Yes      | Yes    | `CMP-{year}-{06d}`               |
| enrollment_id   | str   | Yes      | No     | FK → Enrollment.enrollment_id     |
| employee_id     | str   | Yes      | No     | FK → Employee.employee_id         |
| course_id       | str   | Yes      | No     | FK → Course.course_id             |
| completion_date | date  | Yes      | No     | ≥ enrollment_date                 |
| score           | float | No       | No     | 0–100                             |
| passed          | bool  | Yes      | No     | True if score ≥ 60               |

Completions represent outcomes, not attendance. Duplicate completion events are retained only as labelled ground-truth anomalies and are counted once in outcome metrics.

### 11. Budget

| Field        | Type  | Required | Unique | Allowed Values         | Unit |
|--------------|-------|----------|--------|------------------------|------|
| budget_id    | str   | Yes      | Yes    | `BUD-{dept}-{year}`    |      |
| department   | str   | Yes      | No     | config.DEPARTMENTS     |      |
| year         | int   | Yes      | No     | 2026                   |      |
| total_budget | float | Yes      | No     | 50,000–500,000         | USD  |
| allocated    | float | Yes      | No     | ≥ 0                    | USD  |
| spent        | float | Yes      | No     | Sum of unique employee/course costs in selected learning paths | USD |
| remaining    | float | Yes      | No     | = total_budget − spent | USD  |

`spent` represents planned pathway commitments in this synthetic planning snapshot, not payroll or historical accounting spend. The budget summary is reconciled from unique employee/course `BudgetEvent` records and selected learning paths.

### 12. EnrollmentEvent

| Field         | Type | Required | Unique | Allowed Values |
|---------------|------|----------|--------|----------------|
| event_id      | str  | Yes      | Yes    | `EEV-{06d}` |
| enrollment_id | str  | Yes      | No     | FK → Enrollment.enrollment_id |
| event_type    | str  | Yes      | No     | enrolled, in_progress, completed, dropped, waitlisted |
| event_date    | date | Yes      | No     | ≥ enrollment_date |
| status_after  | str  | Yes      | No     | Same lifecycle enum; latest event matches Enrollment.status |

### 13. BudgetEvent

| Field       | Type  | Required | Unique | Allowed Values |
|-------------|-------|----------|--------|----------------|
| event_id    | str   | Yes      | Yes    | `BGE-{06d}` |
| budget_id   | str   | Yes      | No     | FK → Budget.budget_id |
| employee_id | str   | Yes      | No     | FK → Employee.employee_id |
| course_id   | str   | Yes      | No     | FK → Course.course_id |
| event_type  | str   | Yes      | No     | path_planned, enrollment_committed |
| event_date  | date  | Yes      | No     | Planned start date |
| amount      | float | Yes      | No     | Course cost, USD; non-negative |

**Constraint:** `UNIQUE(budget_id, employee_id, course_id, event_type)`. The sum of `path_planned` event amounts per budget equals `Budget.spent`.

---

## Edge Cases / Anomaly Labels

| Issue Type              | Count | Description                                                      |
|-------------------------|-------|------------------------------------------------------------------|
| prerequisite_violation  | 50    | Rejected recommendation candidate whose prerequisite is not passed |
| budget_exceeded         | 30    | Rejected recommendation candidate that exceeds the remaining budget |
| duplicate_completion    | 25    | Same enrollment has a second labelled completion event            |
| no_reassessment         | 40    | A passed course taught a skill below the employee's role target, but no later assessment exists for that skill |
| course_unavailable      | 35    | Rejected recommendation candidate unavailable in the planning period |

Counts are generation targets and scale with `--starter`; counts may be lower if fewer eligible examples exist. The first, second, and fifth cases label rejected recommendation candidates, not invalid enrollments or committed overspend. `no_reassessment` includes the affected `skill_id`, observed proficiency, and role target so validators can confirm that a real gap remained. All cases are tracked in `ground_truth.csv` / `ground_truth.json`, never leaked into input features.

## Effective dates and lifecycle interpretation

- Role skill targets are static within this synthetic 2026 planning snapshot; no target history is modeled.
- Employee skill assessments are effective on `assessed_date`; the latest assessment for an employee/skill pair is used for gap calculations.
- Course eligibility is based on the overlap between course availability dates and the 2026 planning period. Course `status` is a lifecycle state.
- Enrollment `status` is the current snapshot; `EnrollmentEvent` retains each dated transition. Completion is an outcome event, not an enrollment state substitute.
- Budget is annual and keyed by department/year. `BudgetEvent` records planned pathway commitments; `spent` is reconciled from these commitments and is not accounting history.

---

## ID / Nomenclature Conventions

| Entity           | Format                        | Example                          |
|------------------|-------------------------------|----------------------------------|
| Employee         | `EMP-{06d}`                   | EMP-000001                       |
| Role             | `ROL-{06d}`                   | ROL-000001                       |
| Skill            | `SKL-{06d}`                   | SKL-000001                       |
| RoleSkillTarget  | `RST-{06d}`                   | RST-000001                       |
| EmployeeSkill    | `ESK-{06d}`                   | ESK-000001                       |
| Course           | `CRS-{06d}`                   | CRS-000001                       |
| CourseSkill      | `CSK-{06d}`                   | CSK-000001                       |
| Prerequisite     | `PRQ-{06d}`                   | PRQ-000001                       |
| Enrollment       | `ENR-{emp_id}-{crs_id}`       | ENR-EMP-000042-CRS-000123       |
| Completion       | `CMP-{year}-{06d}`            | CMP-2026-000001                  |
| Budget           | `BUD-{dept}-{year}`           | BUD-Engineering-2026             |

All counters are zero-padded. IDs are immutable once assigned.
