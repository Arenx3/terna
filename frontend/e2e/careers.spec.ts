import AxeBuilder from "@axe-core/playwright"
import { expect, test, type Page } from "@playwright/test"

import { newAdmin } from "./helpers.ts"
import { uniqueEmail } from "./mailpit.ts"

async function expectNoAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze()
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
}

async function createJob(page: Page, title: string, publish: boolean) {
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
