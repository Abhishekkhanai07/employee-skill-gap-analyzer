"""
Configuration module for YottaFlex Skill-Gap Analyzer.
All tuneable parameters, seeds, volumes, and ID formats live here.
"""

# ── Reproducibility ──────────────────────────────────────────────────
RANDOM_SEED = 20261022

# ── Volume Parameters ────────────────────────────────────────────────
NUM_EMPLOYEES = 5_000
NUM_SKILLS = 500
NUM_COURSES = 1_000
NUM_ENROLLMENTS = 10_000
NUM_ROLES = 60          # realistic org has ~50-80 distinct roles
NUM_DEPARTMENTS = 12

# ── Derived Volumes (auto-scaled from primaries) ─────────────────────
ROLE_SKILL_TARGETS_PER_ROLE = (4, 10)       # min, max skills per role
EMPLOYEE_SKILLS_PER_EMP = (3, 15)           # min, max skills assessed
COURSE_SKILLS_PER_COURSE = (1, 4)           # skills a course teaches
PREREQUISITE_CHAIN_MAX_DEPTH = 3
COURSE_CAPACITY_RANGE = (20, 200)
COURSE_COST_RANGE = (50, 5000)              # USD
COURSE_DURATION_RANGE = (4, 120)            # hours
BUDGET_PER_DEPARTMENT = (50_000, 500_000)   # USD per year

# ── Proficiency Scale ────────────────────────────────────────────────
PROFICIENCY_MIN = 1
PROFICIENCY_MAX = 5
# 1=Awareness, 2=Beginner, 3=Intermediate, 4=Advanced, 5=Expert

# ── ID Formats ───────────────────────────────────────────────────────
ID_FORMATS = {
    "employee":        "EMP-{:06d}",
    "role":            "ROL-{:06d}",
    "skill":           "SKL-{:06d}",
    "role_skill_target": "RST-{:06d}",
    "employee_skill":  "ESK-{:06d}",
    "course":          "CRS-{:06d}",
    "course_skill":    "CSK-{:06d}",
    "prerequisite":    "PRQ-{:06d}",
    "enrollment":      "ENR-{emp}-{crs}",
    "completion":      "CMP-{year}-{:06d}",
    "budget":          "BUD-{dept}-{year}",
}

# ── Date Ranges ──────────────────────────────────────────────────────
PLANNING_YEAR = 2026
HIRE_DATE_RANGE = ("2015-01-01", "2026-06-30")
ASSESSMENT_DATE_RANGE = ("2024-01-01", "2026-10-01")
BASELINE_ASSESSMENT_DATE_RANGE = ("2024-01-01", "2025-12-31")
COURSE_AVAILABILITY_RANGE = ("2026-01-01", "2026-12-31")
ENROLLMENT_DATE_RANGE = ("2026-01-01", "2026-10-31")

# ── Lifecycle States ─────────────────────────────────────────────────
EMPLOYEE_STATUSES = ["active", "on_leave", "terminated"]
COURSE_STATUSES = ["active", "inactive", "archived"]
ENROLLMENT_STATUSES = ["enrolled", "in_progress", "completed", "dropped", "waitlisted"]

# ── Skill Categories ────────────────────────────────────────────────
SKILL_CATEGORIES = [
    "Programming", "Data Science", "Cloud", "DevOps", "Security",
    "Project Management", "Communication", "Leadership", "Design",
    "Database", "Networking", "AI/ML", "Business Analysis",
    "Quality Assurance", "Mobile Development",
]

# ── Departments ──────────────────────────────────────────────────────
DEPARTMENTS = [
    "Engineering", "Data Science", "Product", "Design",
    "Marketing", "Sales", "HR", "Finance",
    "Operations", "Legal", "Customer Support", "IT",
]

# ── Edge-Case Injection Counts ───────────────────────────────────────
EDGE_CASES = {
    "prerequisite_violation": 50,
    "budget_exceeded": 30,
    "duplicate_completion": 25,
    "no_reassessment": 40,
    "course_unavailable": 35,
}

# ── Output ───────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
OUTPUT_FORMATS = ["csv", "json"]      # also generates SQL seed
