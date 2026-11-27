import { expect, test } from "@playwright/test"

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
