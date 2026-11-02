import dotenv from "dotenv";
import { fileURLToPath } from "node:url";
import { Pool } from "pg";

import { createApp } from "./app.js";

dotenv.config({ path: fileURLToPath(new URL("../../.env", import.meta.url)) });

const port = Number(process.env.PORT ?? 3001);
const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error("DATABASE_URL is required. Copy .env.example to .env and configure PostgreSQL.");
}

const pool = new Pool({ connectionString: databaseUrl });
const app = createApp(pool);
const server = app.listen(port, () => {
  console.log(`YottaFlex API listening on http://localhost:${port}`);
});

async function shutdown() {
  server.close();
  await pool.end();
}

process.on("SIGINT", () => void shutdown());
process.on("SIGTERM", () => void shutdown());
