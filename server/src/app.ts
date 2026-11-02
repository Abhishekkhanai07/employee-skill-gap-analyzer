import cors from "cors";
import express, { type ErrorRequestHandler } from "express";
import type { Pool } from "pg";

const MAX_PAGE_SIZE = 100;

function queryString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function boundedInteger(value: unknown, fallback: number, maximum: number): number {
  const parsed = typeof value === "string" ? Number(value) : Number.NaN;
  return Number.isInteger(parsed) && parsed > 0 ? Math.min(parsed, maximum) : fallback;
}

export function createApp(pool: Pick<Pool, "query">) {
  const app = express();
  app.use(cors({ origin: process.env.CLIENT_ORIGIN ?? "http://localhost:5173" }));
  app.use(express.json({ limit: "64kb" }));

  app.get("/api/health", async (_request, response) => {
    await pool.query("SELECT 1");
    response.json({ status: "ok", database: "connected" });
  });

  app.get("/api/dashboard/summary", async (_request, response) => {
    const [metrics, budgetRows, topGaps, rejectionRows] = await Promise.all([
      pool.query(`
        WITH skill_assessment_changes AS (
          SELECT assessment_type, current_proficiency,
            LAG(current_proficiency) OVER (
              PARTITION BY employee_id, skill_id
              ORDER BY assessed_date, esk_id
            ) AS prior_proficiency
          FROM employee_skills
        )
        SELECT
          (SELECT COUNT(*) FROM employees)::int AS employees,
          (SELECT COUNT(DISTINCT employee_id) FROM skill_gaps WHERE gap > 0)::int AS employees_with_gaps,
          (SELECT COUNT(*) FROM skill_gaps WHERE gap > 0)::int AS open_skill_gaps,
          COALESCE((SELECT ROUND(AVG(readiness_score)::numeric, 1) FROM career_pathways), 0) AS readiness_score,
          (SELECT COUNT(*) FROM recommendations WHERE recommendation_feasible)::int AS feasible_recommendations,
          (SELECT COUNT(*) FROM recommendations WHERE NOT recommendation_feasible)::int AS rejected_candidates,
          (SELECT COUNT(*) FROM enrollments)::int AS enrollments,
          (SELECT COUNT(DISTINCT enrollment_id) FROM completions)::int AS unique_completions,
          (SELECT COUNT(DISTINCT enrollment_id) FROM completions WHERE passed)::int AS passed_completions,
          (SELECT COUNT(*) - COUNT(DISTINCT enrollment_id) FROM completions)::int AS duplicate_completion_events,
          (SELECT COUNT(*) FROM skill_assessment_changes WHERE assessment_type = 'post_course')::int AS post_course_assessments,
          (SELECT COUNT(*) FROM skill_assessment_changes WHERE assessment_type = 'post_course' AND prior_proficiency IS NOT NULL)::int AS post_course_assessments_with_prior,
          (SELECT COUNT(*) FROM skill_assessment_changes WHERE assessment_type = 'post_course' AND current_proficiency > prior_proficiency)::int AS post_course_assessments_with_gain,
          COALESCE((SELECT ROUND(AVG(current_proficiency - prior_proficiency)::numeric, 2)
            FROM skill_assessment_changes
            WHERE assessment_type = 'post_course' AND prior_proficiency IS NOT NULL), 0) AS average_proficiency_gain
      `),
      pool.query(`
        SELECT department, total_budget, spent, remaining,
          ROUND((spent / NULLIF(total_budget, 0) * 100)::numeric, 1) AS utilization_pct
        FROM budgets
        WHERE year = 2026
        ORDER BY department
      `),
      pool.query(`
        SELECT sg.skill_id, s.skill_name, COUNT(*)::int AS employee_count,
          ROUND(AVG(sg.gap)::numeric, 2) AS average_gap
        FROM skill_gaps sg
        JOIN skills s ON s.skill_id = sg.skill_id
        WHERE sg.gap > 0
        GROUP BY sg.skill_id, s.skill_name
        ORDER BY employee_count DESC, average_gap DESC
        LIMIT 8
      `),
      pool.query(`
        SELECT reason, COUNT(*)::int AS count
        FROM recommendations r
        CROSS JOIN LATERAL unnest(string_to_array(r.rejection_reasons, '|')) AS reason
        WHERE NOT r.recommendation_feasible AND r.rejection_reasons <> ''
        GROUP BY reason
        ORDER BY count DESC, reason
      `),
    ]);

    const row = metrics.rows[0];
    const enrollments = Number(row.enrollments);
    const completions = Number(row.unique_completions);
    response.json({
      ...row,
      readiness_score: Number(row.readiness_score),
      completion_rate: enrollments ? Number((completions / enrollments).toFixed(3)) : 0,
      pass_rate: completions
        ? Number((Number(row.passed_completions) / completions).toFixed(3))
        : 0,
      post_course_skill_gain_rate: Number(row.post_course_assessments_with_prior)
        ? Number((
          Number(row.post_course_assessments_with_gain)
          / Number(row.post_course_assessments_with_prior)
        ).toFixed(3))
        : 0,
      average_proficiency_gain: Number(row.average_proficiency_gain),
      budgets: budgetRows.rows.map((budget) => ({
        ...budget,
        total_budget: Number(budget.total_budget),
        spent: Number(budget.spent),
        remaining: Number(budget.remaining),
        utilization_pct: Number(budget.utilization_pct),
      })),
      top_skill_gaps: topGaps.rows.map((gap) => ({
        ...gap,
        average_gap: Number(gap.average_gap),
      })),
      rejection_reasons: rejectionRows.rows,
    });
  });

  app.get("/api/recommendations", async (request, response) => {
    const limit = boundedInteger(request.query.limit, 25, MAX_PAGE_SIZE);
    const page = boundedInteger(request.query.page, 1, 100_000);
    const offset = (page - 1) * limit;
    const filters = ["($1::boolean OR r.recommendation_feasible = TRUE)"];
    const parameters: unknown[] = [request.query.includeRejected === "true"];
    const department = queryString(request.query.department);
    const skill = queryString(request.query.skill);
    const search = queryString(request.query.search);

    if (department) {
      parameters.push(department);
      filters.push(`e.department = $${parameters.length}`);
    }
    if (skill) {
      parameters.push(skill);
      filters.push(`(r.skill_id = $${parameters.length} OR s.skill_name ILIKE '%' || $${parameters.length} || '%')`);
    }
    if (search) {
      parameters.push(search);
      filters.push(`(r.employee_id ILIKE '%' || $${parameters.length} || '%' OR e.first_name ILIKE '%' || $${parameters.length} || '%' OR e.last_name ILIKE '%' || $${parameters.length} || '%' OR r.course_name ILIKE '%' || $${parameters.length} || '%')`);
    }

    parameters.push(limit, offset);
    const result = await pool.query(`
      SELECT r.employee_id, e.first_name, e.last_name, e.department,
        r.skill_id, s.skill_name, r.gap, r.recommended_course_id,
        r.course_name, r.course_cost, r.meets_prerequisites, r.within_budget,
        r.available, r.capacity_available, r.recommendation_feasible,
        r.rejection_reasons, r.recommendation_rank,
        COUNT(*) OVER()::int AS total_count
      FROM recommendations r
      JOIN employees e ON e.employee_id = r.employee_id
      JOIN skills s ON s.skill_id = r.skill_id
      WHERE ${filters.join(" AND ")}
      ORDER BY r.recommendation_feasible DESC, r.recommendation_rank,
        e.department, r.employee_id, r.skill_id
      LIMIT $${parameters.length - 1} OFFSET $${parameters.length}
    `, parameters);

    response.json({
      page,
      limit,
      total: result.rows.length ? Number(result.rows[0].total_count) : 0,
      recommendations: result.rows,
    });
  });

  app.get("/api/career-pathways", async (request, response) => {
    const department = queryString(request.query.department);
    const parameters: unknown[] = [];
    const where = department
      ? (parameters.push(department), `WHERE e.department = $${parameters.length}`)
      : "";
    const result = await pool.query(`
      SELECT cp.*, e.department
      FROM career_pathways cp
      JOIN employees e ON e.employee_id = cp.employee_id
      ${where}
      ORDER BY cp.readiness_score DESC, cp.employee_id
      LIMIT 100
    `, parameters);
    response.json({ career_pathways: result.rows });
  });

  const errorHandler: ErrorRequestHandler = (error, _request, response, _next) => {
    console.error("API request failed:", error);
    response.status(500).json({ error: "Request failed; check the server logs." });
  };
  app.use(errorHandler);
  return app;
}
