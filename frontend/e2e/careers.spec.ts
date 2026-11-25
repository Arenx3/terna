import { expect, test } from "@playwright/test"

import {
  createJob,
  expectNoAccessibilityViolations,
  newAdmin,
  RESUME_PDF,
} from "./helpers.ts"
import { uniqueEmail, waitForEmail } from "./mailpit.ts"

test("anyone can read a company's open jobs, and nothing else", async ({
  page,
  browser,
}) => {
  await newAdmin(page, uniqueEmail("careers"), "Careers E2E", "Ana Pérez")
  const openId = await createJob(page, "Legal Counsel", true)
  const draftId = await createJob(page, "Secret Draft", false)

  await page.goto("/jobs")
  const careersLink = page.getByRole("link", { name: "Careers page" })
  const careersPath = new URL(
    (await careersLink.getAttribute("href")) ?? "",
    "http://x"
  ).pathname

  // A visitor: no session at all.
  const visitorContext = await browser.newContext({ locale: "en-US" })
  const visitor = await visitorContext.newPage()
  await visitor.goto(careersPath)
  await expect(
    visitor.getByRole("heading", { level: 1, name: "Work at Careers E2E" })
  ).toBeVisible()
  await expect(visitor.getByText("1 open position")).toBeVisible()
  await expect(visitor.getByText("Secret Draft")).toHaveCount(0)
  await expectNoAccessibilityViolations(visitor)

  await visitor.getByRole("link", { name: /Legal Counsel/ }).click()
  await expect(
    visitor.getByRole("heading", { level: 1, name: "Legal Counsel" })
  ).toBeVisible()
  await expect(
    visitor.getByRole("heading", { name: "What we're looking for" })
  ).toBeVisible()
  await expect(visitor).toHaveTitle("Legal Counsel · Careers E2E")
  await expectNoAccessibilityViolations(visitor)
  // Contrast holds on paper too.
  await visitor.evaluate(() => localStorage.setItem("terna.theme", "light"))
  await visitor.reload()
  await expect(
    visitor.getByRole("heading", { level: 1, name: "Legal Counsel" })
  ).toBeVisible()
  await expectNoAccessibilityViolations(visitor)

  const posting = JSON.parse(
    (await visitor
      .locator('script[type="application/ld+json"]')
      .textContent()) ?? "{}"
  )
  expect(posting).toMatchObject({
    "@type": "JobPosting",
    title: "Legal Counsel",
    hiringOrganization: { name: "Careers E2E" },
    jobLocation: { address: { addressCountry: "MX" } },
  })
  expect(posting.url).toContain(`${careersPath}/jobs/${openId}`)

  // Drafts are not public, even with the exact link.
  await visitor.goto(`${careersPath}/jobs/${draftId}`)
  await expect(
    visitor.getByRole("heading", { name: "This page doesn't exist" })
  ).toBeVisible()
  await visitorContext.close()
})

test("a candidate applies with a résumé and the team sees them", async ({
  page,
  browser,
}) => {
  await newAdmin(page, uniqueEmail("apply"), "Apply E2E", "Ana Pérez")
  const jobId = await createJob(page, "Payroll Analyst", true)
  await page.goto("/jobs")
  const careersPath = new URL(
    (await page
      .getByRole("link", { name: "Careers page" })
      .getAttribute("href")) ?? "",
    "http://x"
  ).pathname

  const visitorContext = await browser.newContext({ locale: "en-US" })
  const visitor = await visitorContext.newPage()
  await visitor.goto(`${careersPath}/jobs/${jobId}`)
  await visitor.getByRole("link", { name: "Apply", exact: true }).click()
  // The form gets its token as it appears: time the visit from there.
  await expect(visitor.getByLabel("Full name")).toBeVisible()
  const opened = Date.now()

  const candidate = uniqueEmail("candidate")
  await visitor.getByLabel("Full name").fill("Lucía Torres")
  await visitor.getByLabel("Email").fill(candidate)
  await visitor.locator('input[type="file"]').setInputFiles({
    name: "cv-lucia.pdf",
    mimeType: "application/pdf",
    buffer: RESUME_PDF,
  })
  await expect(visitor.getByText("cv-lucia.pdf")).toBeVisible()

  // Consent comes first: without it, nothing is sent.
  await visitor.getByRole("button", { name: "Send application" }).click()
  await expect(
    visitor.getByText("Accept the privacy notice to apply.")
  ).toBeVisible()
  await visitor
    .getByRole("checkbox", { name: /I've read and accept the privacy notice/ })
    .check()

  // A person takes a few seconds to fill a form; the API refuses instant ones.
  await visitor.waitForTimeout(Math.max(0, 3_500 - (Date.now() - opened)))
  await visitor.getByRole("button", { name: "Send application" }).click()
  await expect(
    visitor.getByRole("heading", { name: "Done, Lucía!" })
  ).toBeVisible({ timeout: 20_000 })
  await expectNoAccessibilityViolations(visitor)
  await visitorContext.close()

  const email = await waitForEmail(candidate, /We received your application/)
  expect(email.text).toContain("Payroll Analyst")

  // On the job's board, in the first stage, with the résumé one menu away.
  await page.goto(`/jobs/${jobId}/candidates`)
  const applied = page.getByRole("region", { name: /^Applied/ })
  await expect(applied).toContainText("Lucía Torres")
  await expect(applied).toContainText(candidate)
  await page.getByRole("button", { name: "Actions for Lucía Torres" }).click()
  await expect(
    page.getByRole("menuitem", { name: "Download Lucía Torres's résumé" })
  ).toBeVisible()
})
