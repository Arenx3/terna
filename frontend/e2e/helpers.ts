import AxeBuilder from "@axe-core/playwright"
import { expect, type Browser, type Page } from "@playwright/test"

import { appLink, waitForEmail } from "./mailpit.ts"

export const PASSWORD = "e2e-correct-horse-battery-7"

export async function signUp(
  page: Page,
  email: string,
  { company = "Acme E2E", name = "Ana Pérez" } = {}
) {
  await page.goto("/signup")
  await page.getByLabel("Company name").fill(company)
  await page.getByLabel("Your full name").fill(name)
  await page.getByLabel("Work email").fill(email)
  await page.getByLabel("Password").fill(PASSWORD)
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(
    page.getByRole("heading", { name: "Check your inbox" })
  ).toBeVisible()
}

export async function verify(page: Page, email: string) {
  const message = await waitForEmail(email, /Verify your email/)
  await page.goto(appLink(message.text, "/verify-email"))
  await expect(
    page.getByRole("heading", { name: "Email confirmed" })
  ).toBeVisible()
}

export async function logIn(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: "Log in" }).click()
}

/** Sign up, confirm the address and log in: ready on the home page. */
export async function newAdmin(
  page: Page,
  email: string,
  company: string,
  name: string
) {
  await signUp(page, email, { company, name })
  await verify(page, email)
  await logIn(page, email)
  await expect(
    page.getByRole("heading", { name: `Welcome, ${name.split(" ")[0]}` })
  ).toBeVisible()
}

export async function expectNoAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze()
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
}

/** Create a job with one requirement; returns its id. */
export async function createJob(page: Page, title: string, publish: boolean) {
  await page.goto("/jobs/new")
  await page.getByLabel("Job title").fill(title)
  await page.getByLabel("Location").fill("Querétaro, Qro.")
  const requirement = page.getByRole("textbox", { name: "New requirement" })
  await requirement.fill("Contract law")
  await requirement.press("Enter")
  await page
    .getByRole("button", { name: publish ? "Publish" : "Save draft" })
    .click()
  await expect(page).toHaveURL(/\/jobs\/[0-9a-f-]{36}$/)
  return page.url().split("/").at(-1) ?? ""
}

/** The signed-in company's careers page path, from the jobs list. */
export async function careersPathOf(page: Page) {
  await page.goto("/jobs")
  const href = await page
    .getByRole("link", { name: "Careers page" })
    .getAttribute("href")
  return new URL(href ?? "", "http://x").pathname
}

export const RESUME_PDF = Buffer.from(
  [
    "%PDF-1.4",
    "1 0 obj << /Type /Catalog >> endobj",
    "trailer << /Root 1 0 R >>",
    "%%EOF",
  ].join(String.fromCharCode(10))
)

/** Apply to a job as an anonymous visitor, in a browser of their own. */
export async function applyAs(
  browser: Browser,
  jobPath: string,
  candidate: { name: string; email: string }
) {
  const context = await browser.newContext({ locale: "en-US" })
  const visitor = await context.newPage()
  await visitor.goto(jobPath)
  await expect(visitor.getByLabel("Full name")).toBeVisible()
  // The form gets its token as it appears; the API refuses instant submissions.
  const opened = Date.now()
  await visitor.getByLabel("Full name").fill(candidate.name)
  await visitor.getByLabel("Email").fill(candidate.email)
  await visitor.locator('input[type="file"]').setInputFiles({
    name: "cv.pdf",
    mimeType: "application/pdf",
    buffer: RESUME_PDF,
  })
  await visitor
    .getByRole("checkbox", { name: /I've read and accept the privacy notice/ })
    .check()
  await visitor.waitForTimeout(Math.max(0, 3_500 - (Date.now() - opened)))
  await visitor.getByRole("button", { name: "Send application" }).click()
  await expect(visitor.getByRole("heading", { name: /^Done, / })).toBeVisible({
    timeout: 20_000,
  })
  await context.close()
}
