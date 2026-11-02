"""
master_data.py — Core synthetic data generator for master/parent entities.

Generates the foundational reference tables that all transactional data
depends on: skills, roles, employees, courses, and departmental budgets.
Every random operation flows through a single numpy Generator seeded from
``config.RANDOM_SEED`` so that runs are fully reproducible.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from faker import Faker

import config


# ---------------------------------------------------------------------------
# Predefined realistic data pools
# ---------------------------------------------------------------------------

_SKILL_TEMPLATES: list[str] = [
    # Programming & Development
    "Python Programming", "Java Development", "JavaScript Development",
    "TypeScript Development", "C++ Programming", "C# Development",
    "Go Programming", "Rust Programming", "Ruby Development",
    "Kotlin Development", "Swift Programming", "PHP Development",
    "Scala Programming", "R Programming", "MATLAB Programming",
    # Web & Frontend
    "React.js Development", "Angular Development", "Vue.js Development",
    "Next.js Development", "HTML5 & CSS3", "Svelte Development",
    "Tailwind CSS", "Web Accessibility", "Progressive Web Apps",
    # Backend & APIs
    "Node.js Development", "Django Development", "Flask Development",
    "Spring Boot Development", "REST API Design", "GraphQL Development",
    "gRPC Development", "Microservices Architecture",
    # Cloud & Infrastructure
    "AWS Lambda", "AWS EC2 Management", "Azure Cloud Services",
    "Google Cloud Platform", "Cloud Architecture", "Serverless Computing",
    "Infrastructure as Code", "Terraform", "Kubernetes Administration",
    "Docker Containerization", "Cloud Cost Optimization",
    # Data & Analytics
    "SQL Optimization", "PostgreSQL Administration", "MongoDB Management",
    "Data Warehousing", "ETL Pipeline Design", "Apache Spark",
    "Apache Kafka", "Data Modeling", "Business Intelligence",
    "Tableau Visualization", "Power BI", "Data Governance",
    # Machine Learning & AI
    "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Computer Vision", "Reinforcement Learning", "MLOps",
    "TensorFlow Development", "PyTorch Development", "LLM Fine-Tuning",
    "Generative AI", "Feature Engineering", "Model Deployment",
    # DevOps & SRE
    "CI/CD Pipeline Design", "Jenkins Administration", "GitHub Actions",
    "Site Reliability Engineering", "Monitoring & Observability",
    "Incident Management", "Load Testing", "Chaos Engineering",
    # Security
    "Cybersecurity Fundamentals", "Penetration Testing", "OWASP Security",
    "Identity & Access Management", "Encryption & Cryptography",
    "Security Compliance", "Threat Modeling", "SOC Operations",
    # Project & Process
    "Agile Methodology", "Scrum Framework", "Kanban Management",
    "Project Management", "Product Management", "Stakeholder Management",
    "Risk Management", "Change Management", "Six Sigma",
    # Soft Skills & Leadership
    "Technical Leadership", "Team Management", "Communication Skills",
    "Presentation Skills", "Conflict Resolution", "Mentoring & Coaching",
    "Strategic Planning", "Decision Making",
    # Quality & Testing
    "Unit Testing", "Integration Testing", "Test Automation",
    "Selenium Testing", "Performance Testing", "Quality Assurance",
    # Networking & Systems
    "Network Administration", "Linux Administration",
    "Windows Server Management", "DNS & Load Balancing",
    "Firewall Configuration",
]

_CATEGORY_PREFIXES: dict[str, list[str]] = {
    "Technical": [
        "Advanced", "Applied", "Practical", "Modern", "Enterprise",
        "Scalable", "High-Performance", "Production-Grade",
    ],
    "Leadership": [
        "Strategic", "Executive", "Organizational", "Cross-Functional",
        "Transformational", "Visionary",
    ],
    "Communication": [
        "Effective", "Professional", "Executive-Level", "Cross-Cultural",
        "Persuasive", "Collaborative",
    ],
    "Analytical": [
        "Quantitative", "Statistical", "Predictive", "Exploratory",
        "Advanced", "Applied",
    ],
    "Creative": [
        "Innovative", "Design-Driven", "Human-Centered", "UX-Focused",
        "Creative", "Visual",
    ],
    "Management": [
        "Operational", "Tactical", "Strategic", "Portfolio",
        "Program-Level", "Enterprise",
    ],
}

_CATEGORY_SUFFIXES: dict[str, list[str]] = {
    "Technical": [
        "Engineering", "Development", "Implementation", "Architecture",
        "Optimization", "Integration", "Automation",
    ],
    "Leadership": [
        "Leadership", "Governance", "Coaching", "Facilitation",
        "Strategy", "Alignment",
    ],
    "Communication": [
        "Writing", "Storytelling", "Negotiation", "Facilitation",
        "Reporting", "Presentation",
    ],
    "Analytical": [
        "Analysis", "Modeling", "Research", "Forecasting",
        "Interpretation", "Evaluation",
    ],
    "Creative": [
        "Thinking", "Prototyping", "Ideation", "Design",
        "Storytelling", "Branding",
    ],
    "Management": [
        "Coordination", "Planning", "Execution", "Oversight",
        "Budgeting", "Reporting",
    ],
}

_PROVIDERS: list[str] = [
    "Coursera", "Udemy", "LinkedIn Learning", "Internal Training",
    "AWS Training", "Google Cloud Training", "Microsoft Learn",
    "Pluralsight", "edX", "Codecademy", "DataCamp", "O'Reilly Media",
    "Skillsoft", "A Cloud Guru", "Udacity", "Khan Academy",
    "HarvardX", "Stanford Online", "MIT OpenCourseWare",
    "Company Workshop",
]

_COURSE_NAME_PATTERNS: list[str] = [
    "Introduction to {skill}",
    "Advanced {skill}",
    "{skill} Masterclass",
    "{skill} Fundamentals",
    "{skill} for Professionals",
    "{skill} Bootcamp",
    "{skill} Certification Prep",
    "{skill} Best Practices",
    "Hands-On {skill}",
    "{skill} in Practice",
]

_ROLE_TEMPLATES: list[str] = [
    "Software Engineer", "Data Scientist", "Data Engineer",
    "DevOps Engineer", "Cloud Architect", "Product Manager",
    "Project Manager", "Business Analyst", "QA Engineer",
    "Security Engineer", "Machine Learning Engineer",
    "Frontend Developer", "Backend Developer", "Full Stack Developer",
    "Site Reliability Engineer", "Technical Writer",
    "UX Designer", "Solutions Architect", "Database Administrator",
    "Systems Administrator", "Network Engineer", "Scrum Master",
    "Engineering Manager", "Data Analyst", "Platform Engineer",
    "Release Manager", "IT Support Specialist", "Compliance Analyst",
    "Training Coordinator", "HR Business Partner",
]

_LEVELS: list[str] = ["junior", "mid", "senior", "lead", "principal", "director"]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _iso(d: date) -> str:
    """Return an ISO-8601 date string (YYYY-MM-DD)."""
    return d.isoformat()


def _random_date_between(
    rng: np.random.Generator,
    start: date,
    end: date,
    size: int = 1,
) -> list[date]:
    """Return *size* random dates uniformly distributed in [start, end]."""
    delta_days = (end - start).days
    if delta_days <= 0:
        return [start] * size
    offsets = rng.integers(0, delta_days + 1, size=size)
    return [start + timedelta(days=int(o)) for o in offsets]


# ---------------------------------------------------------------------------
# 1. Skills
# ---------------------------------------------------------------------------

def generate_skills(rng: np.random.Generator) -> pd.DataFrame:
    """Generate ``config.NUM_SKILLS`` unique, realistically named skills.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded random generator for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: skill_id, skill_name, category, description
    """
    num: int = config.NUM_SKILLS
    categories: list[str] = list(config.SKILL_CATEGORIES)

    # Start with the hand-curated template list
    unique_names: list[str] = list(_SKILL_TEMPLATES[:])

    # Generate more names by combining category prefixes/suffixes with base words
    _base_words: list[str] = [
        "Data", "Cloud", "API", "System", "Platform", "Pipeline",
        "Workflow", "Process", "Service", "Network", "Database",
        "Security", "Testing", "Deployment", "Migration", "Monitoring",
        "Compliance", "Documentation", "Visualization", "Reporting",
        "Collaboration", "Innovation", "Optimization", "Scaling",
        "Debugging", "Refactoring", "Architecture", "Prototyping",
        "Benchmarking", "Auditing",
    ]

    # Expand until we have enough unique names
    for cat in categories:
        prefixes = _CATEGORY_PREFIXES.get(cat, ["Advanced", "Applied"])
        suffixes = _CATEGORY_SUFFIXES.get(cat, ["Development", "Management"])
        for prefix in prefixes:
            for suffix in suffixes:
                candidate = f"{prefix} {suffix}"
                if candidate not in unique_names:
                    unique_names.append(candidate)
                if len(unique_names) >= num:
                    break
            if len(unique_names) >= num:
                break
        if len(unique_names) >= num:
            break

    # If still short, combine prefixes with base words
    if len(unique_names) < num:
        for cat in categories:
            prefixes = _CATEGORY_PREFIXES.get(cat, ["Advanced"])
            for prefix in prefixes:
                for base in _base_words:
                    candidate = f"{prefix} {base} Skills"
                    if candidate not in unique_names:
                        unique_names.append(candidate)
                    if len(unique_names) >= num:
                        break
                if len(unique_names) >= num:
                    break
            if len(unique_names) >= num:
                break

    # Final fallback: numbered variants
    idx = 1
    while len(unique_names) < num:
        candidate = f"Specialized Skill {idx:03d}"
        if candidate not in unique_names:
            unique_names.append(candidate)
        idx += 1

    # Shuffle and trim to exact count
    selected_names = unique_names[:num]
    rng.shuffle(selected_names)  # type: ignore[arg-type]

    # Assign categories
    cat_assignments = rng.choice(categories, size=num)

    records: list[dict[str, Any]] = []
    for i in range(num):
        skill_id = f"SKL-{i + 1:06d}"
        skill_name = selected_names[i]
        category = str(cat_assignments[i])
        description = f"Proficiency in {skill_name.lower()} within the {category.lower()} domain."
        records.append(
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "category": category,
                "description": description,
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 2. Roles
# ---------------------------------------------------------------------------

def generate_roles(rng: np.random.Generator) -> pd.DataFrame:
    """Generate ``config.NUM_ROLES`` unique, realistically named roles.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded random generator for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: role_id, role_name, department, level, description
    """
    num: int = config.NUM_ROLES
    departments: list[str] = list(config.DEPARTMENTS)

    # Build unique role names by combining level labels with role templates
    _level_labels: dict[str, str] = {
        "junior": "Junior",
        "mid": "",
        "senior": "Senior",
        "lead": "Lead",
        "principal": "Principal",
        "director": "Director of",
    }

    unique_roles: list[tuple[str, str, str]] = []  # (role_name, dept, level)
    seen_names: set[str] = set()

    # Shuffle templates & departments for variety
    templates = list(_ROLE_TEMPLATES)
    rng.shuffle(templates)  # type: ignore[arg-type]

    for template in templates:
        for level in _LEVELS:
            label = _level_labels[level]
            if label:
                if level == "director":
                    name = f"{label} {template}"
                else:
                    name = f"{label} {template}"
            else:
                name = template

            if name not in seen_names:
                dept = str(rng.choice(departments))
                seen_names.add(name)
                unique_roles.append((name, dept, level))

            if len(unique_roles) >= num:
                break
        if len(unique_roles) >= num:
            break

    # Fallback if we still need more
    extra_idx = 1
    while len(unique_roles) < num:
        name = f"Specialist Role {extra_idx:03d}"
        if name not in seen_names:
            dept = str(rng.choice(departments))
            level = str(rng.choice(_LEVELS))
            seen_names.add(name)
            unique_roles.append((name, dept, level))
        extra_idx += 1

    unique_roles = unique_roles[:num]

    records: list[dict[str, Any]] = []
    for i, (role_name, department, level) in enumerate(unique_roles):
        role_id = f"ROL-{i + 1:06d}"
        description = (
            f"{role_name} in the {department} department — "
            f"responsible for {level}-level contributions."
        )
        records.append(
            {
                "role_id": role_id,
                "role_name": role_name,
                "department": department,
                "level": level,
                "description": description,
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 3. Employees
# ---------------------------------------------------------------------------

def generate_employees(
    rng: np.random.Generator,
    roles_df: pd.DataFrame,
) -> pd.DataFrame:
    """Generate ``config.NUM_EMPLOYEES`` employees with consistent role/dept mapping.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded random generator for reproducibility.
    roles_df : pd.DataFrame
        The roles DataFrame (must contain role_id, department).

    Returns
    -------
    pd.DataFrame
        Columns: employee_id, first_name, last_name, email, department,
        role_id, hire_date, status
    """
    num: int = config.NUM_EMPLOYEES
    fake = Faker()
    Faker.seed(int(rng.integers(0, 2**31)))

    # Build role → department lookup
    role_ids: list[str] = roles_df["role_id"].tolist()
    role_dept: dict[str, str] = dict(
        zip(roles_df["role_id"], roles_df["department"])
    )

    # Assign roles to employees
    assigned_role_indices = rng.integers(0, len(role_ids), size=num)
    assigned_roles = [role_ids[int(idx)] for idx in assigned_role_indices]

    # Generate hire dates
    hire_start, hire_end = config.HIRE_DATE_RANGE
    if isinstance(hire_start, str):
        hire_start = date.fromisoformat(hire_start)
    if isinstance(hire_end, str):
        hire_end = date.fromisoformat(hire_end)
    hire_dates = _random_date_between(rng, hire_start, hire_end, size=num)

    # Status distribution: ~90% active, ~5% on_leave, ~5% terminated
    status_choices = rng.choice(
        ["active", "on_leave", "terminated"],
        size=num,
        p=[0.90, 0.05, 0.05],
    )

    # Generate names and ensure unique emails
    email_counts: dict[str, int] = {}
    records: list[dict[str, Any]] = []

    for i in range(num):
        employee_id = f"EMP-{i + 1:06d}"
        first_name: str = fake.first_name()
        last_name: str = fake.last_name()

        # Build unique email
        base_email = f"{first_name.lower()}.{last_name.lower()}@example.test"
        if base_email in email_counts:
            email_counts[base_email] += 1
            email = (
                f"{first_name.lower()}.{last_name.lower()}"
                f"{email_counts[base_email]}@yottaflex.ai"
            )
        else:
            email_counts[base_email] = 0
            email = base_email

        rid = assigned_roles[i]
        department = role_dept[rid]

        records.append(
            {
                "employee_id": employee_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "department": department,
                "role_id": rid,
                "hire_date": _iso(hire_dates[i]),
                "status": str(status_choices[i]),
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 4. Courses
# ---------------------------------------------------------------------------

def generate_courses(
    rng: np.random.Generator,
    skills_df: pd.DataFrame,
) -> pd.DataFrame:
    """Generate ``config.NUM_COURSES`` courses with names related to skills.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded random generator for reproducibility.
    skills_df : pd.DataFrame
        The skills DataFrame (used to derive course names).

    Returns
    -------
    pd.DataFrame
        Columns: course_id, course_name, provider, duration_hours, cost,
        capacity, availability_start, availability_end, status
    """
    num: int = config.NUM_COURSES
    skill_names: list[str] = skills_df["skill_name"].tolist()

    # Pre-generate all course names (unique)
    course_names: list[str] = []
    seen_course_names: set[str] = set()

    # Cycle through skills × patterns to build names
    patterns = list(_COURSE_NAME_PATTERNS)
    for skill in skill_names:
        for pattern in patterns:
            name = pattern.format(skill=skill)
            if name not in seen_course_names:
                seen_course_names.add(name)
                course_names.append(name)
            if len(course_names) >= num:
                break
        if len(course_names) >= num:
            break

    # Fallback if still short
    extra_idx = 1
    while len(course_names) < num:
        name = f"Specialized Training Module {extra_idx:03d}"
        if name not in seen_course_names:
            seen_course_names.add(name)
            course_names.append(name)
        extra_idx += 1

    # Shuffle and trim
    selected_names = course_names[:num]
    rng.shuffle(selected_names)  # type: ignore[arg-type]

    # Parse availability range
    avail_start_bound, avail_end_bound = config.COURSE_AVAILABILITY_RANGE
    if isinstance(avail_start_bound, str):
        avail_start_bound = date.fromisoformat(avail_start_bound)
    if isinstance(avail_end_bound, str):
        avail_end_bound = date.fromisoformat(avail_end_bound)

    dur_lo, dur_hi = config.COURSE_DURATION_RANGE
    cost_lo, cost_hi = config.COURSE_COST_RANGE
    cap_lo, cap_hi = config.COURSE_CAPACITY_RANGE

    # Status distribution: ~85% active, ~10% inactive, ~5% archived
    statuses = rng.choice(
        ["active", "inactive", "archived"],
        size=num,
        p=[0.85, 0.10, 0.05],
    )

    # Random vectors
    durations = rng.integers(dur_lo, dur_hi + 1, size=num)
    costs = np.round(rng.uniform(cost_lo, cost_hi, size=num), 2)
    capacities = rng.integers(cap_lo, cap_hi + 1, size=num)
    provider_indices = rng.integers(0, len(_PROVIDERS), size=num)
    start_dates = _random_date_between(rng, avail_start_bound, avail_end_bound, size=num)
    end_offsets = rng.integers(30, 181, size=num)  # 30-180 days after start

    records: list[dict[str, Any]] = []
    for i in range(num):
        course_id = f"CRS-{i + 1:06d}"
        avail_start = start_dates[i]
        avail_end = avail_start + timedelta(days=int(end_offsets[i]))
        records.append(
            {
                "course_id": course_id,
                "course_name": selected_names[i],
                "provider": _PROVIDERS[int(provider_indices[i])],
                "duration_hours": int(durations[i]),
                "cost": float(costs[i]),
                "capacity": int(capacities[i]),
                "availability_start": _iso(avail_start),
                "availability_end": _iso(avail_end),
                "status": str(statuses[i]),
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 5. Budgets
# ---------------------------------------------------------------------------

def generate_budgets(rng: np.random.Generator) -> pd.DataFrame:
    """Generate one budget row per department for the planning year.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded random generator for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: budget_id, department, year, total_budget, allocated,
        spent, remaining
    """
    departments: list[str] = list(config.DEPARTMENTS)
    year: int = config.PLANNING_YEAR
    budget_lo, budget_hi = config.BUDGET_PER_DEPARTMENT

    records: list[dict[str, Any]] = []
    for dept in departments:
        budget_id = f"BUD-{dept}-{year}"
        total_budget = float(
            np.round(rng.uniform(budget_lo, budget_hi), 2)
        )
        allocated = total_budget
        spent = 0.0
        remaining = total_budget

        records.append(
            {
                "budget_id": budget_id,
                "department": dept,
                "year": year,
                "total_budget": total_budget,
                "allocated": allocated,
                "spent": spent,
                "remaining": remaining,
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_all_master_data(
    seed: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Generate every master/parent entity table in dependency order.

    Parameters
    ----------
    seed : int or None
        Explicit seed for the numpy random generator.  Falls back to
        ``config.RANDOM_SEED`` when *None*.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys: ``"skills"``, ``"roles"``, ``"employees"``, ``"courses"``,
        ``"budgets"``.
    """
    rng = np.random.default_rng(seed if seed is not None else config.RANDOM_SEED)

    skills_df = generate_skills(rng)
    roles_df = generate_roles(rng)
    employees_df = generate_employees(rng, roles_df)
    courses_df = generate_courses(rng, skills_df)
    budgets_df = generate_budgets(rng)

    return {
        "skills": skills_df,
        "roles": roles_df,
        "employees": employees_df,
        "courses": courses_df,
        "budgets": budgets_df,
    }


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data = generate_all_master_data()
    for name, df in data.items():
        print(f"\n{'=' * 60}")
        print(f"  {name.upper()}  —  {len(df)} rows, {list(df.columns)}")
        print(f"{'=' * 60}")
        print(df.head(5).to_string(index=False))
