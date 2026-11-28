import { expect, test, type Page } from "@playwright/test"

import {
  applyAs,
  careersPathOf,
  createJob,
  expectNoAccessibilityViolations,
  newAdmin,
} from "./helpers.ts"
import { uniqueEmail } from "./mailpit.ts"

test("a new résumé is read into sections the team can check", async ({
  page,
  browser,
}) => {
  await newAdmin(page, uniqueEmail("screening"), "Screening E2E", "Ana Pérez")
  const jobId = await createJob(page, "Data Engineer", true)
  const careersPath = await careersPathOf(page)
  await applyAs(browser, `${careersPath}/jobs/${jobId}`, {
    name: "Lucía Torres",
    email: uniqueEmail("lucia"),
  })

  await page.goto(`/jobs/${jobId}/candidates`)
  await page.getByRole("link", { name: "Lucía Torres" }).click()
  const panel = page.getByRole("dialog", { name: "Lucía Torres" })
  await panel.getByRole("tab", { name: "Résumé" }).click()

  // A worker reads the file after the application arrives; the panel checks back.
  const experience = panel.getByRole("region", { name: "Experience" })
  await expect(experience).toBeVisible({ timeout: 30_000 })
  await expect(experience.getByText("Jan 2020 – Present")).toBeVisible()
  await expect(
    panel
      .getByRole("region", { name: "Languages" })
      .getByText("Spanish (native), English (C1)")
  ).toBeVisible()
  await expect(panel.getByText("5 passages read · 1 page")).toBeVisible()
  await expectNoAccessibilityViolations(page)

  // What the AI reads: the same text, with the personal data hidden.
  const header = panel.getByRole("region", { name: "Header" })
  await expect(header.getByText("Lucía Torres")).toBeVisible()
  await panel.getByRole("button", { name: "What the AI sees" }).click()
  await expect(panel.getByText(/with 3 personal details hidden/)).toBeVisible()
  await expect(header.getByText("Lucía Torres")).toHaveCount(0)
  await expect(header.getByText("name", { exact: true })).toBeVisible()
  await expect(experience.getByText("Jan 2020 – Present")).toBeVisible()
  await expectNoAccessibilityViolations(page)

  // The original file is one click away.
  await panel.getByRole("button", { name: "Document" }).click()
  await expect(panel.getByRole("button", { name: "Document" })).toHaveAttribute(
    "aria-pressed",
    "true"
  )
  await expect(panel.locator("iframe")).toBeVisible()
})

/** A published job whose requirements the test résumé meets, and one it doesn't. */
async function jobFor(page: Page, title: string) {
  await page.goto("/jobs/new")
  await page.getByLabel("Job title").fill(title)
  await page.getByLabel("Location").fill("Querétaro, Qro.")
  const requirement = page.getByRole("textbox", { name: "New requirement" })
  for (const text of ["Python pipelines", "Contract law"]) {
    await requirement.fill(text)
    await requirement.press("Enter")
  }
  await page.getByRole("button", { name: "Publish" }).click()
  await expect(page).toHaveURL(/\/jobs\/[0-9a-f-]{36}$/)
  return page.url().split("/").at(-1) ?? ""
}

test("each requirement gets a verdict with its evidence highlighted", async ({
  page,
  browser,
}) => {
  // The first screening on a fresh stack also loads the local model.
  test.setTimeout(240_000)
  await newAdmin(page, uniqueEmail("matching"), "Matching E2E", "Ana Pérez")
  const jobId = await jobFor(page, "Data Engineer")
  const careersPath = await careersPathOf(page)

  // The board is open when the application arrives: its card fills in live.
  await page.goto(`/jobs/${jobId}/candidates`)
  await applyAs(browser, `${careersPath}/jobs/${jobId}`, {
    name: "Lucía Torres",
    email: uniqueEmail("lucia"),
  })
  await expect(page.getByText("1/2 must")).toBeVisible({ timeout: 180_000 })
  await expect(
    page.getByRole("img", {
      name: "Must-haves: 1 of 2 met, 0 partly.",
    })
  ).toBeVisible()

  await page.getByRole("link", { name: "Lucía Torres" }).click()
  const panel = page.getByRole("dialog", { name: "Lucía Torres" })
  const python = panel
    .getByRole("listitem")
    .filter({ hasText: "Python pipelines" })
  await expect(python.getByText("Meets", { exact: true })).toBeVisible()
  await expect(
    python.locator("mark", { hasText: "Python" }).first()
  ).toBeVisible()
  const law = panel.getByRole("listitem").filter({ hasText: "Contract law" })
  await expect(law.getByText("No evidence", { exact: true })).toBeVisible()
  await expect(law.locator("mark")).toHaveCount(0)
  await expectNoAccessibilityViolations(page)

  // The same evidence, where it sits in the résumé.
  await python.getByRole("button", { name: "Show in résumé" }).click()
  await expect(panel.getByRole("tab", { name: "Résumé" })).toHaveAttribute(
    "aria-selected",
    "true"
  )
  await expect(panel.getByText("Evidence for")).toBeVisible()
  const experience = panel.getByRole("region", { name: "Experience" })
  await expect(experience.locator("mark", { hasText: "Python" })).toBeVisible()
  await panel.getByRole("button", { name: "Clear" }).click()
  await expect(experience.locator("mark")).toHaveCount(0)
})
