# YottaFlex Skill-Gap & Learning Planner

A locally runnable demo that connects role skill targets and employee assessments to gap analysis, prerequisite-aware course recommendations, annual budgets, learning paths, and career readiness.

## What is implemented

- **Synthetic data:** reproducible Python generator; default scale is 5,000 employees, 500 skills, 1,000 courses, and 10,000 enrollments.
- **Decision rules:** recommendations are marked feasible only when the skill target is met by the course, prerequisites have been passed, the course intersects the planning period, capacity remains, and department budget can cover the unique employee/course commitment.
- **Traceable events:** enrollment lifecycle changes are appended to `EnrollmentEvent`; completions are separate from attendance/enrollment. Post-course proficiency assessments are append-only `EmployeeSkill` records linked to their source completion; duplicate completion records are retained and labelled rather than overwritten.
- **Exceptions and labels:** rejected prerequisite, budget, availability candidates, duplicate completions, and completions without reassessment are recorded in a separate `ground_truth.csv` / `ground_truth.json`. Ground truth is excluded from SQL seed input and API features.
- **Database and API:** PostgreSQL relational schema and Express API expose metrics, feasible recommendations, rejected candidates, budget health, and career pathways.
- **UI:** React + TypeScript dashboard with Recharts for skill-gap and budget views, plus employee/course search, department filtering, and an option to inspect rejected candidates.
- **Validation:** primary/foreign-key checks, ID uniqueness, lifecycle/date checks, prerequisite ordering, budget reconciliation, and recommendation constraint checks. Expected injected anomalies are visible as validation warnings.

The project uses synthetic data only. Faker-generated names and `example.test` emails are not real employee records. No external dataset is used; generated artifacts include a source manifest with the seed and row counts.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Node.js, Express, TypeScript |
| Database | PostgreSQL 16 |
| Data generation | Python, pandas, NumPy, Faker |
| Tests | pytest and Vitest |
| Charts | Recharts |

## Architecture

- `src/generators/` builds seeded master data, relationships, and traceable lifecycle events.
- `src/logic/` calculates proficiency gaps, feasible recommendations, learning plans, career readiness, and outcome metrics.
- `src/validation/` checks keys, references, lifecycle transitions, capacity, recommendation constraints, budgets, and labelled exceptions.
- `src/export/` writes CSV, JSON, SQL seed files, SHA-256 source manifest, validation summary, and outcome summary.
- `database/schema.sql` defines the PostgreSQL tables, keys, constraints, and indexes.
- `server/src/` contains the Express API; dashboard metrics and career-pathway records are queried from PostgreSQL.
- `client/src/` contains the React + TypeScript dashboard and Recharts visualizations.
- `tests/` contains Python generator/business-rule tests and Vitest API tests.

## Requirements

- Python 3.10 or later
- Node.js 22 LTS and npm
- Docker Desktop (or a local PostgreSQL 16 server)

## Windows quick start

From the project directory, in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
docker compose up -d db
```

If PowerShell says `docker` is not recognized after installing Docker Desktop, restart the terminal (or VS Code) so it reloads PATH. For a per-user Docker Desktop install, the bundled CLI can be called directly:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" compose up -d db
```

Generate and validate the smaller starter dataset first:

```powershell
python main.py --starter
python main.py --validate-only
```

Generate the full requested baseline instead:

```powershell
python main.py
python main.py --validate-only
```

Generation writes CSV, JSON, SQL seed data, `manifest.json` / `source_manifest.json` (with SHA-256 checksums), `validation_summary.json`, `outcome_summary.json`, and separate ground-truth files to `output\`. The output directory is ignored by Git because the dataset can be regenerated from the code and fixed seed.

Load the generated SQL into the local PostgreSQL container (run once per fresh database):

```powershell
$containerId = docker compose ps -q db
docker cp database\schema.sql "$($containerId):/tmp/schema.sql"
docker compose exec -T db psql -U yottaflex -d yottaflex -v ON_ERROR_STOP=1 -f /tmp/schema.sql
docker cp output\seed.sql "$($containerId):/tmp/seed.sql"
docker compose exec -T db psql -U yottaflex -d yottaflex -v ON_ERROR_STOP=1 -f /tmp/seed.sql
```

Start the API and frontend in development mode:

```powershell
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The API listens on port 3001 and the Vite development server proxies `/api` requests to it. `GET /api/health` checks the database connection.

## Tests and verification

```powershell
python -m pytest -q
npm test
npm run build
```

Verify deterministic generation by running:

```powershell
python main.py --reproduce
```

The reproducibility report is written to `output\reproducibility_report.json`; it compares generated master and transaction tables with the same seed. The default seed is `20261022`; override it with `--seed`.

## Data and decision notes

- The complete field-level dictionary, constraints, and relationship cardinalities are in [docs/data_dictionary.md](docs/data_dictionary.md); the machine-readable entity schema is [src/schema.py](src/schema.py).
- PostgreSQL constraints and indexes are in [database/schema.sql](database/schema.sql).
- Skill gaps are `max(target proficiency - latest assessed proficiency, 0)`. Employees without an assessment for a targeted skill start at proficiency 0.
- A course can be recommended only when it teaches the skill at the target level and is active, available during 2026, has remaining capacity, fits the employee department's remaining budget, and its prerequisites have passed. Waitlisted and dropped enrollments do not consume course capacity.
- Only feasible rank-1 recommendations are sequenced into learning paths. Missing prerequisite courses are surfaced for review, not silently added to a path.
- `Budget.spent` in the generated planning snapshot is the sum of unique employee/course costs in selected learning paths; it is not represented as historical accounting spend.
- `recommendations.csv` contains candidate decisions and rejection reasons. Only feasible rank-1 recommendations are sequenced into learning paths.
- `completion_rate` counts distinct enrollments with completion events. `pass_rate` is calculated from distinct completion outcomes, not attendance.
- Post-course skill-gain metrics compare an assessment with the previous assessment for that employee/skill; assessments without a prior comparison are reported separately and are not counted as proficiency gains.
- Career readiness is the share of the employee's targeted skills meeting their current role targets. The next role is the next configured level in the same department; a pathway row is not a promotion decision.
- The starter mode scales all primary volumes to 10% while keeping the same generation rules and seed. The full mode defaults to the exact requested primary volumes.
- The five exception labels are source-grounded: prerequisite, budget, and availability labels point to rejected candidates; duplicate completion labels the extra event; missing-reassessment labels require a passed course that teaches a below-target role skill with no later assessment for that skill.
- The checked-in `docs/source_manifest.json` and `docs/validation_summary.json` are generated full-volume evidence snapshots for seed `20261022`. Regenerate the full data to produce current exports under `output\`.

## Provenance and AI-use disclosure

All records are generated locally from seeded Python randomness and Faker; no public/private employee dataset is imported. AI assistance was used for implementation and verification under the prompts recorded in [prompt_history/copilot_prompts.md](prompt_history/copilot_prompts.md). The project author should review, understand, and be prepared to explain all business rules, assumptions, and limitations before submission.

## Known limitations

- This is a local review/demo application, not an authenticated production HR system. Do not load real employee data.
- Courses that fail a prerequisite are surfaced as rejected candidates; the planner does not automatically add missing prerequisite courses as path steps.
- The generator emits the requested anomaly examples at configured scale; starter mode scales the edge-case counts as well.
- PostgreSQL is not bundled as a binary. Use Docker Compose or point `DATABASE_URL` in `.env` at a local PostgreSQL 16 instance.
- Generated datasets are not committed; the manifest records their row counts and checksums so they can be regenerated and verified.

## Verification

Verified with seed `20261022`:

| Check | Result |
|---|---|
| Full-scale generation | 5,000 employees, 500 skills, 1,000 courses, 10,000 enrollments |
| Full-data validation | 87 checks: 86 passed, 0 failed, 1 expected warning for labelled duplicate completion events |
| Full-output reproducibility | Two complete runs matched row counts and SHA-256 checksums for all 39 generated data/summary files |
| Python tests | 9 passed |
| Vitest API tests | 6 passed |
| Production build | Client and server built successfully; Vite reports a 619 KB minified client chunk |
| Dependency audit | 0 vulnerabilities |
| PostgreSQL smoke test | Schema and starter seed loaded; API health returned `database: connected`; summary and career-pathway endpoints returned database records |

The expected duplicate-completion warning is preserved in ground truth and counted once in completion-rate metrics. The large-client-chunk warning is non-fatal.
