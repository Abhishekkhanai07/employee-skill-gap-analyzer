CREATE TABLE IF NOT EXISTS roles (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('junior', 'mid', 'senior', 'lead', 'principal', 'director')),
    description TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    role_id TEXT NOT NULL REFERENCES roles(role_id),
    hire_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'on_leave', 'terminated'))
);

CREATE TABLE IF NOT EXISTS courses (
    course_id TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    duration_hours INTEGER NOT NULL CHECK (duration_hours > 0),
    cost NUMERIC(10, 2) NOT NULL CHECK (cost >= 0),
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    availability_start DATE NOT NULL,
    availability_end DATE NOT NULL CHECK (availability_end >= availability_start),
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'archived'))
);

CREATE TABLE IF NOT EXISTS budgets (
    budget_id TEXT PRIMARY KEY,
    department TEXT NOT NULL,
    year INTEGER NOT NULL,
    total_budget NUMERIC(12, 2) NOT NULL CHECK (total_budget > 0),
    allocated NUMERIC(12, 2) NOT NULL CHECK (allocated >= 0),
    spent NUMERIC(12, 2) NOT NULL CHECK (spent >= 0),
    remaining NUMERIC(12, 2) NOT NULL,
    UNIQUE (department, year),
    CHECK (ABS(total_budget - spent - remaining) <= 0.01),
    CHECK (spent <= total_budget)
);

CREATE TABLE IF NOT EXISTS budget_events (
    event_id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL REFERENCES budgets(budget_id),
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('path_planned', 'enrollment_committed')),
    event_date DATE NOT NULL,
    amount NUMERIC(10, 2) NOT NULL CHECK (amount >= 0),
    UNIQUE (budget_id, employee_id, course_id, event_type)
);

CREATE TABLE IF NOT EXISTS role_skill_targets (
    rst_id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL REFERENCES roles(role_id),
    skill_id TEXT NOT NULL REFERENCES skills(skill_id),
    target_proficiency SMALLINT NOT NULL CHECK (target_proficiency BETWEEN 1 AND 5),
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    UNIQUE (role_id, skill_id)
);

CREATE TABLE IF NOT EXISTS course_skills (
    csk_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    skill_id TEXT NOT NULL REFERENCES skills(skill_id),
    skill_level_gained SMALLINT NOT NULL CHECK (skill_level_gained BETWEEN 1 AND 5),
    UNIQUE (course_id, skill_id)
);

CREATE TABLE IF NOT EXISTS prerequisites (
    prq_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    prerequisite_course_id TEXT NOT NULL REFERENCES courses(course_id),
    CHECK (course_id <> prerequisite_course_id),
    UNIQUE (course_id, prerequisite_course_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    enrollment_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('enrolled', 'in_progress', 'completed', 'dropped', 'waitlisted')),
    UNIQUE (employee_id, course_id)
);

CREATE TABLE IF NOT EXISTS enrollment_events (
    event_id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('enrolled', 'in_progress', 'completed', 'dropped', 'waitlisted')),
    event_date DATE NOT NULL,
    status_after TEXT NOT NULL CHECK (status_after IN ('enrolled', 'in_progress', 'completed', 'dropped', 'waitlisted'))
);

CREATE TABLE IF NOT EXISTS completions (
    completion_id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    completion_date DATE NOT NULL,
    score NUMERIC(5, 2) CHECK (score BETWEEN 0 AND 100),
    passed BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_skills (
    esk_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    skill_id TEXT NOT NULL REFERENCES skills(skill_id),
    current_proficiency SMALLINT NOT NULL CHECK (current_proficiency BETWEEN 1 AND 5),
    assessed_date DATE NOT NULL,
    assessment_type TEXT NOT NULL CHECK (assessment_type IN ('baseline', 'post_course')),
    source_completion_id TEXT REFERENCES completions(completion_id),
    CHECK (
        (assessment_type = 'baseline' AND source_completion_id IS NULL)
        OR (assessment_type = 'post_course' AND source_completion_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS skill_gaps (
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    role_id TEXT NOT NULL REFERENCES roles(role_id),
    skill_id TEXT NOT NULL REFERENCES skills(skill_id),
    skill_name TEXT NOT NULL,
    target_proficiency SMALLINT NOT NULL CHECK (target_proficiency BETWEEN 1 AND 5),
    current_proficiency SMALLINT NOT NULL CHECK (current_proficiency BETWEEN 0 AND 5),
    gap SMALLINT NOT NULL CHECK (gap BETWEEN 0 AND 5),
    priority TEXT NOT NULL,
    PRIMARY KEY (employee_id, skill_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    skill_id TEXT NOT NULL REFERENCES skills(skill_id),
    gap SMALLINT NOT NULL CHECK (gap > 0),
    recommended_course_id TEXT NOT NULL REFERENCES courses(course_id),
    course_name TEXT NOT NULL,
    course_cost NUMERIC(10, 2) NOT NULL CHECK (course_cost >= 0),
    meets_prerequisites BOOLEAN NOT NULL,
    within_budget BOOLEAN NOT NULL,
    available BOOLEAN NOT NULL,
    capacity_available BOOLEAN NOT NULL,
    recommendation_feasible BOOLEAN NOT NULL,
    rejection_reasons TEXT NOT NULL DEFAULT '',
    recommendation_rank INTEGER NOT NULL CHECK (recommendation_rank > 0),
    CHECK (
        NOT recommendation_feasible
        OR (meets_prerequisites AND within_budget AND available AND capacity_available)
    )
);

CREATE TABLE IF NOT EXISTS learning_paths (
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    path_step INTEGER NOT NULL CHECK (path_step > 0),
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    course_name TEXT NOT NULL,
    skill_id TEXT NOT NULL REFERENCES skills(skill_id),
    estimated_start DATE NOT NULL,
    estimated_end DATE NOT NULL CHECK (estimated_end >= estimated_start),
    cumulative_cost NUMERIC(12, 2) NOT NULL CHECK (cumulative_cost >= 0),
    cumulative_hours NUMERIC(12, 2) NOT NULL CHECK (cumulative_hours >= 0),
    PRIMARY KEY (employee_id, path_step)
);

CREATE TABLE IF NOT EXISTS career_pathways (
    employee_id TEXT PRIMARY KEY REFERENCES employees(employee_id),
    current_role TEXT NOT NULL,
    current_level TEXT NOT NULL,
    next_role TEXT NOT NULL,
    next_level TEXT NOT NULL,
    total_gaps INTEGER NOT NULL CHECK (total_gaps >= 0),
    critical_gaps INTEGER NOT NULL CHECK (critical_gaps >= 0),
    courses_needed INTEGER NOT NULL CHECK (courses_needed >= 0),
    estimated_cost NUMERIC(12, 2) NOT NULL CHECK (estimated_cost >= 0),
    estimated_hours NUMERIC(12, 2) NOT NULL CHECK (estimated_hours >= 0),
    readiness_score NUMERIC(5, 2) NOT NULL CHECK (readiness_score BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS idx_employee_skills_latest
    ON employee_skills (employee_id, skill_id, assessed_date DESC);
CREATE INDEX IF NOT EXISTS idx_course_skills_skill
    ON course_skills (skill_id, course_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_feasible
    ON recommendations (recommendation_feasible, recommendation_rank);
CREATE INDEX IF NOT EXISTS idx_recommendations_employee
    ON recommendations (employee_id, skill_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course_status
    ON enrollments (course_id, status);
CREATE INDEX IF NOT EXISTS idx_enrollment_events_timeline
    ON enrollment_events (enrollment_id, event_date, event_id);
