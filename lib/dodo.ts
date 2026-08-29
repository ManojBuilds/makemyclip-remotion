import { DodoPayments } from "dodopayments"

const environment =
  (process.env.DODO_PAYMENTS_ENVIRONMENT as "live_mode" | "test_mode") ||
  (process.env.NODE_ENV === "production" ? "live_mode" : "test_mode")

const apiKey = process.env.DODO_PAYMENTS_API_KEY

if (!apiKey) {
  console.warn(
    "[DODO_PAYMENTS] Warning: DODO_PAYMENTS_API_KEY environment variable is not defined!"
  )
}

export const dodo = new DodoPayments({
  bearerToken: apiKey || "",
  webhookKey: process.env.DODO_PAYMENTS_WEBHOOK_KEY || "",
  environment,
})

