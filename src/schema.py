"""
Schema definitions and data dictionary for the Skill-Gap Analyzer.

Every entity is described with:
  - field name, type, required/optional, allowed values, units, uniqueness, validation rules
  - primary keys, foreign keys, cardinality, lifecycle states, effective dates
"""

SCHEMA = {
    "Employee": {
        "description": "Master record for every employee in the organisation.",
        "primary_key": "employee_id",
        "fields": {
            "employee_id":  {"type": "str",  "required": True,  "format": "EMP-{06d}", "unique": True},
            "first_name":   {"type": "str",  "required": True},
            "last_name":    {"type": "str",  "required": True},
            "email":        {"type": "str",  "required": True,  "unique": True, "validation": "valid email"},
            "department":   {"type": "str",  "required": True,  "allowed": "config.DEPARTMENTS"},
            "role_id":      {"type": "str",  "required": True,  "fk": "Role.role_id"},
            "hire_date":    {"type": "date", "required": True,  "validation": "<= today"},
            "status":       {"type": "str",  "required": True,  "allowed": ["active","on_leave","terminated"]},
        },
        "relationships": {
            "Role":           {"cardinality": "N:1", "fk": "role_id",     "required": True},
            "EmployeeSkill":  {"cardinality": "1:N", "via": "employee_id"},
            "Enrollment":     {"cardinality": "1:N", "via": "employee_id"},
        },
    },
    "Role": {
        "description": "Job roles within the organisation hierarchy.",
        "primary_key": "role_id",
        "fields": {
            "role_id":      {"type": "str",  "required": True,  "format": "ROL-{06d}", "unique": True},
            "role_name":    {"type": "str",  "required": True,  "unique": True},
            "department":   {"type": "str",  "required": True,  "allowed": "config.DEPARTMENTS"},
            "level":        {"type": "str",  "required": True,  "allowed": ["junior","mid","senior","lead","principal","director"]},
            "description":  {"type": "str",  "required": False},
        },
        "relationships": {
            "Employee":         {"cardinality": "1:N", "via": "role_id"},
            "RoleSkillTarget":  {"cardinality": "1:N", "via": "role_id"},
        },
    },
    "Skill": {
        "description": "Discrete, assessable skills that can be targeted by roles and taught by courses.",
        "primary_key": "skill_id",
        "fields": {
            "skill_id":     {"type": "str",  "required": True,  "format": "SKL-{06d}", "unique": True},
            "skill_name":   {"type": "str",  "required": True,  "unique": True},
            "category":     {"type": "str",  "required": True,  "allowed": "config.SKILL_CATEGORIES"},
            "description":  {"type": "str",  "required": False},
        },
        "relationships": {
            "RoleSkillTarget":  {"cardinality": "1:N", "via": "skill_id"},
            "EmployeeSkill":    {"cardinality": "1:N", "via": "skill_id"},
            "CourseSkill":      {"cardinality": "1:N", "via": "skill_id"},
        },
    },
    "RoleSkillTarget": {
        "description": "Defines the target proficiency a role requires for a specific skill.",
        "primary_key": "rst_id",
        "fields": {
            "rst_id":               {"type": "str",  "required": True,  "format": "RST-{06d}", "unique": True},
            "role_id":              {"type": "str",  "required": True,  "fk": "Role.role_id"},
            "skill_id":             {"type": "str",  "required": True,  "fk": "Skill.skill_id"},
            "target_proficiency":   {"type": "int",  "required": True,  "allowed": [1,2,3,4,5], "unit": "proficiency level"},
            "priority":             {"type": "str",  "required": True,  "allowed": ["critical","high","medium","low"]},
        },
        "constraints": ["UNIQUE(role_id, skill_id)"],
        "relationships": {
            "Role":  {"cardinality": "N:1", "fk": "role_id", "required": True},
            "Skill": {"cardinality": "N:1", "fk": "skill_id", "required": True},
        },
    },
    "EmployeeSkill": {
        "description": "Assessment record: an employee's proficiency in a skill at a point in time. Event-sourced — new assessments are appended, never overwritten.",
        "primary_key": "esk_id",
        "fields": {
            "esk_id":               {"type": "str",  "required": True,  "format": "ESK-{06d}", "unique": True},
            "employee_id":          {"type": "str",  "required": True,  "fk": "Employee.employee_id"},
            "skill_id":             {"type": "str",  "required": True,  "fk": "Skill.skill_id"},
            "current_proficiency":  {"type": "int",  "required": True,  "allowed": [1,2,3,4,5]},
            "assessed_date":        {"type": "date", "required": True},
            "assessment_type":      {"type": "str",  "required": True,  "allowed": ["baseline","post_course"]},
            "source_completion_id":{"type": "str",  "required": False, "fk": "Completion.completion_id"},
        },
        "constraints": ["Latest assessment per (employee_id, skill_id) is the current proficiency"],
        "relationships": {
            "Employee": {"cardinality": "N:1", "fk": "employee_id", "required": True},
            "Skill":    {"cardinality": "N:1", "fk": "skill_id",    "required": True},
            "Completion": {"cardinality": "N:1", "fk": "source_completion_id", "required": False},
        },
    },
    "Course": {
        "description": "Training course with cost, duration, capacity and availability window.",
        "primary_key": "course_id",
        "fields": {
            "course_id":            {"type": "str",   "required": True,  "format": "CRS-{06d}", "unique": True},
            "course_name":          {"type": "str",   "required": True},
            "provider":             {"type": "str",   "required": True},
            "duration_hours":       {"type": "int",   "required": True,  "unit": "hours", "validation": "> 0"},
            "cost":                 {"type": "float", "required": True,  "unit": "USD",   "validation": ">= 0"},
            "capacity":             {"type": "int",   "required": True,  "validation": "> 0"},
            "availability_start":   {"type": "date",  "required": True},
            "availability_end":     {"type": "date",  "required": True,  "validation": ">= availability_start"},
            "status":               {"type": "str",   "required": True,  "allowed": ["active","inactive","archived"]},
        },
        "relationships": {
            "CourseSkill":   {"cardinality": "1:N", "via": "course_id"},
            "Prerequisite":  {"cardinality": "1:N", "via": "course_id"},
            "Enrollment":    {"cardinality": "1:N", "via": "course_id"},
        },
    },
    "CourseSkill": {
        "description": "Bridge table: which skills a course teaches and to what level.",
        "primary_key": "csk_id",
        "fields": {
            "csk_id":              {"type": "str", "required": True,  "format": "CSK-{06d}", "unique": True},
            "course_id":           {"type": "str", "required": True,  "fk": "Course.course_id"},
            "skill_id":            {"type": "str", "required": True,  "fk": "Skill.skill_id"},
            "skill_level_gained":  {"type": "int", "required": True,  "allowed": [1,2,3,4,5]},
        },
        "constraints": ["UNIQUE(course_id, skill_id)"],
        "relationships": {
            "Course": {"cardinality": "N:1", "fk": "course_id", "required": True},
            "Skill":  {"cardinality": "N:1", "fk": "skill_id",  "required": True},
        },
    },
    "Prerequisite": {
        "description": "Directed prerequisite edge: course_id requires prerequisite_course_id to be completed first.",
        "primary_key": "prq_id",
        "fields": {
            "prq_id":                   {"type": "str", "required": True,  "format": "PRQ-{06d}", "unique": True},
            "course_id":                {"type": "str", "required": True,  "fk": "Course.course_id"},
            "prerequisite_course_id":   {"type": "str", "required": True,  "fk": "Course.course_id"},
        },
        "constraints": [
            "UNIQUE(course_id, prerequisite_course_id)",
            "course_id != prerequisite_course_id",
            "No circular prerequisite chains",
        ],
        "relationships": {
            "Course (target)":   {"cardinality": "N:1", "fk": "course_id",             "required": True},
            "Course (prereq)":   {"cardinality": "N:1", "fk": "prerequisite_course_id", "required": True},
        },
    },
    "Enrollment": {
        "description": "Event record: an employee enrolling in a course. Tracks lifecycle.",
        "primary_key": "enrollment_id",
        "fields": {
            "enrollment_id":    {"type": "str",  "required": True,  "format": "ENR-{emp_id}-{crs_id}", "unique": True},
            "employee_id":      {"type": "str",  "required": True,  "fk": "Employee.employee_id"},
            "course_id":        {"type": "str",  "required": True,  "fk": "Course.course_id"},
            "enrollment_date":  {"type": "date", "required": True},
            "status":           {"type": "str",  "required": True,  "allowed": ["enrolled","in_progress","completed","dropped","waitlisted"]},
        },
        "relationships": {
            "Employee":   {"cardinality": "N:1", "fk": "employee_id", "required": True},
            "Course":     {"cardinality": "N:1", "fk": "course_id",   "required": True},
            "Completion": {"cardinality": "1:0..N", "via": "enrollment_id", "note": "duplicate events are labelled anomalies"},
            "EnrollmentEvent": {"cardinality": "1:N", "via": "enrollment_id"},
        },
    },
    "Completion": {
        "description": "Records successful or failed course completion, linked to an enrollment.",
        "primary_key": "completion_id",
        "fields": {
            "completion_id":    {"type": "str",   "required": True,  "format": "CMP-{year}-{06d}", "unique": True},
            "enrollment_id":    {"type": "str",   "required": True,  "fk": "Enrollment.enrollment_id"},
            "employee_id":      {"type": "str",   "required": True,  "fk": "Employee.employee_id"},
            "course_id":        {"type": "str",   "required": True,  "fk": "Course.course_id"},
            "completion_date":  {"type": "date",  "required": True,  "validation": ">= enrollment_date"},
            "score":            {"type": "float", "required": False, "validation": "0-100"},
            "passed":           {"type": "bool",  "required": True},
        },
        "relationships": {
            "Enrollment": {"cardinality": "1:1", "fk": "enrollment_id", "required": True},
            "Employee":   {"cardinality": "N:1", "fk": "employee_id",   "required": True},
            "Course":     {"cardinality": "N:1", "fk": "course_id",     "required": True},
        },
    },
    "Budget": {
        "description": "Annual training budget per department. Planned pathway spend reconciles to BudgetEvent records.",
        "primary_key": "budget_id",
        "fields": {
            "budget_id":      {"type": "str",   "required": True,  "format": "BUD-{dept}-{year}", "unique": True},
            "department":     {"type": "str",   "required": True,  "allowed": "config.DEPARTMENTS"},
            "year":           {"type": "int",   "required": True},
            "total_budget":   {"type": "float", "required": True,  "unit": "USD", "validation": "> 0"},
            "allocated":      {"type": "float", "required": True,  "unit": "USD", "validation": ">= 0"},
            "spent":          {"type": "float", "required": True,  "unit": "USD", "validation": ">= 0"},
            "remaining":      {"type": "float", "required": True,  "unit": "USD", "validation": "= total_budget - spent"},
        },
        "constraints": ["spent <= total_budget (except deliberate edge cases)", "remaining = total_budget - spent"],
        "relationships": {
            "Department": {"cardinality": "1:1", "fk": "department", "note": "Logical link via department name"},
            "BudgetEvent": {"cardinality": "1:N", "via": "budget_id"},
        },
    },
    "EnrollmentEvent": {
        "description": "Append-only event history for enrollment lifecycle changes.",
        "primary_key": "event_id",
        "fields": {
            "event_id": {"type": "str", "required": True, "format": "EEV-{06d}", "unique": True},
            "enrollment_id": {"type": "str", "required": True, "fk": "Enrollment.enrollment_id"},
            "event_type": {"type": "str", "required": True, "allowed": ["enrolled","in_progress","completed","dropped","waitlisted"]},
            "event_date": {"type": "date", "required": True},
            "status_after": {"type": "str", "required": True, "allowed": ["enrolled","in_progress","completed","dropped","waitlisted"]},
        },
        "relationships": {
            "Enrollment": {"cardinality": "N:1", "fk": "enrollment_id", "required": True},
        },
    },
    "BudgetEvent": {
        "description": "Traceable planned spend allocation linked to a budget, employee, and course.",
        "primary_key": "event_id",
        "fields": {
            "event_id": {"type": "str", "required": True, "format": "BGE-{06d}", "unique": True},
            "budget_id": {"type": "str", "required": True, "fk": "Budget.budget_id"},
            "employee_id": {"type": "str", "required": True, "fk": "Employee.employee_id"},
            "course_id": {"type": "str", "required": True, "fk": "Course.course_id"},
            "event_type": {"type": "str", "required": True, "allowed": ["path_planned","enrollment_committed"]},
            "event_date": {"type": "date", "required": True},
            "amount": {"type": "float", "required": True, "unit": "USD", "validation": ">= 0"},
        },
        "constraints": ["UNIQUE(budget_id, employee_id, course_id, event_type)"],
        "relationships": {
            "Budget": {"cardinality": "N:1", "fk": "budget_id", "required": True},
            "Employee": {"cardinality": "N:1", "fk": "employee_id", "required": True},
            "Course": {"cardinality": "N:1", "fk": "course_id", "required": True},
        },
    },
}
