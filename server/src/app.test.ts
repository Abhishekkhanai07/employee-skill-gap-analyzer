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
