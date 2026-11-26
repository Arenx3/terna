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

// WinAnsi (cp1252) for the few typographic characters outside Latin-1.
const WIN_ANSI: Record<string, number> = { "•": 0x95, "–": 0x96, "—": 0x97 }
const winAnsi = (text: string) =>
  Buffer.from(
    Array.from(
      text,
      (c) => WIN_ANSI[c] ?? (c.charCodeAt(0) < 256 ? c.charCodeAt(0) : 63)
    )
  )

/** A one-page PDF with real text (Helvetica, WinAnsi), so the résumé parser has something to read. */
export function textPdf(lines: string[]): Buffer {
  const escape = (text: string) => text.replace(/[()\\]/g, (c) => `\\${c}`)
  const content = [
    "BT",
    "/F1 11 Tf",
    "56 780 Td",
    ...lines.flatMap((line, i) => [
      ...(i ? ["0 -18 Td"] : []),
      `(${escape(line)}) Tj`,
    ]),
    "ET",
  ].join("\n")
  const stream = winAnsi(content)
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] " +
      "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
  ].map((body) => Buffer.from(body))
  objects.push(
    Buffer.concat([
      Buffer.from(`<< /Length ${stream.length} >>\nstream\n`),
      stream,
      Buffer.from("\nendstream"),
    ])
  )
  const parts: Buffer[] = [Buffer.from("%PDF-1.4\n")]
  let size = parts[0].length
  const offsets: number[] = []
  objects.forEach((body, index) => {
    offsets.push(size)
    const object = Buffer.concat([
      Buffer.from(`${index + 1} 0 obj\n`),
      body,
      Buffer.from("\nendobj\n"),
    ])
    parts.push(object)
    size += object.length
  })
  const xref = [
    "xref",
    `0 ${objects.length + 1}`,
    "0000000000 65535 f ",
    ...offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n `),
    "trailer",
    `<< /Size ${objects.length + 1} /Root 1 0 R >>`,
    "startxref",
    String(size),
    "%%EOF",
    "",
  ].join("\n")
  return Buffer.concat([...parts, Buffer.from(xref)])
}

export const RESUME_PDF = textPdf([
  "Lucía Torres",
  "Data engineer · Ciudad de México · lucia.torres@example.com",
  "Experience",
  "Data Engineer, Acme (Jan 2020 – Present)",
  "• Ingestion pipelines in Python and Airflow.",
  "Languages",
  "Spanish (native), English (C1)",
])

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
