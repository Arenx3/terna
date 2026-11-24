import { defineConfig, devices } from "@playwright/test"

/**
 * End-to-end tests against a running stack (`docker compose up -d --wait`),
 * reading the emails it sends through Mailpit's API.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    locale: "en-US",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
})
