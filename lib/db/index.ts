import { neon } from "@neondatabase/serverless"
import { drizzle as drizzleNeon } from "drizzle-orm/neon-http"
import postgres from "postgres"
import { drizzle as drizzlePostgresJs } from "drizzle-orm/postgres-js"
import * as schema from "./schema"

const databaseUrl = process.env.DATABASE_URL
if (!databaseUrl) {
  throw new Error("DATABASE_URL is required")
}

const driver =
  process.env.DB_DRIVER ??
  (process.env.VERCEL ? "neon-http" : undefined) ??
  (/\.neon\.tech\b/i.test(databaseUrl) ? "neon-http" : "postgres-js")

declare global {
   
  var __makemyclip_postgres_client: ReturnType<typeof postgres> | undefined
   
  var __makemyclip_neon_sql: ReturnType<typeof neon> | undefined
}

export const db =
  driver === "neon-http"
    ? drizzleNeon((globalThis.__makemyclip_neon_sql ??= neon(databaseUrl)), {
        schema,
      })
    : drizzlePostgresJs({
        client: (globalThis.__makemyclip_postgres_client ??= postgres(
          databaseUrl,
          {
            ssl: databaseUrl.includes("sslmode=require")
              ? "require"
              : undefined,
          }
        )),
        schema,
      })
