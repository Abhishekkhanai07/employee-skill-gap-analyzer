import { afterEach, describe, expect, it, vi } from "vitest";
import type { Pool } from "pg";

import { createApp } from "./app.js";

const servers: Array<{ close: (callback?: (error?: Error) => void) => void }> = [];

async function requestApi(
  query: ReturnType<typeof vi.fn>,
  path: string,
) {
  const app = createApp({ query } as unknown as Pick<Pool, "query">);
  const server = app.listen(0);
  servers.push(server);
  await new Promise<void>((resolve) => server.once("listening", resolve));
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("Test server did not bind to a TCP port.");
  }
  const response = await fetch(`http://127.0.0.1:${address.port}${path}`);
  return { response, server };
}

afterEach(async () => {
  await Promise.all(servers.splice(0).map(
    (server) => new Promise<void>((resolve, reject) =>
      server.close((error) => error ? reject(error) : resolve())
    ),
  ));
});

describe("recommendations API", () => {
  it("uses safe, parameterized filters and caps the requested page size", async () => {
    const query = vi.fn().mockResolvedValue({ rows: [] });
    const { response } = await requestApi(
      query,
      "/api/recommendations?limit=9999&page=2&department=Engineering&search=EMP-1",
    );
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload).toEqual({ page: 2, limit: 100, total: 0, recommendations: [] });
    expect(query).toHaveBeenCalledOnce();
    const [sql, values] = query.mock.calls[0];
    expect(sql).toContain("LIMIT $4 OFFSET $5");
    expect(sql).toContain("e.department = $2");
    expect(sql).toContain("e.first_name ILIKE '%' || $3 || '%'");
    expect(values).toEqual([false, "Engineering", "EMP-1", 100, 100]);
  });
});

describe("dashboard metrics API", () => {
  it("reports employee and measured post-course skill outcomes from database results", async () => {
    const metrics = {
      employees: 500,
      employees_with_gaps: 486,
      open_skill_gaps: 1554,
      readiness_score: "50.4",
      feasible_recommendations: 565,
      rejected_candidates: 3159,
      enrollments: 1000,
      unique_completions: 758,
      passed_completions: 658,
      duplicate_completion_events: 2,
      post_course_assessments: 200,
      post_course_assessments_with_prior: 190,
      post_course_assessments_with_gain: 150,
      average_proficiency_gain: "0.78",
    };
    const query = vi.fn().mockImplementation((sql: string) =>
      Promise.resolve({ rows: sql.includes("WITH skill_assessment_changes") ? [metrics] : [] })
    );
    const { response } = await requestApi(query, "/api/dashboard/summary");
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.employees).toBe(500);
    expect(payload.completion_rate).toBe(0.758);
    expect(payload.pass_rate).toBe(0.868);
    expect(payload.post_course_skill_gain_rate).toBe(0.789);
    expect(payload.average_proficiency_gain).toBe(0.78);
    expect(query.mock.calls[0][0]).toContain("LAG(current_proficiency)");
  });
});

describe("career pathways API", () => {
  it("returns pathway records and parameterizes the department filter", async () => {
    const pathway = { employee_id: "EMP-000001", department: "Engineering" };
    const query = vi.fn().mockResolvedValue({ rows: [pathway] });
    const { response } = await requestApi(
      query,
      "/api/career-pathways?department=Engineering",
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ career_pathways: [pathway] });
    expect(query.mock.calls[0][0]).toContain("WHERE e.department = $1");
    expect(query.mock.calls[0][1]).toEqual(["Engineering"]);
  });
});
