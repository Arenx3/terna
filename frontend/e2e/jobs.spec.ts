import { expect, test } from "@playwright/test"

import { newAdmin } from "./helpers.ts"
import { uniqueEmail } from "./mailpit.ts"

test("a recruiter writes a job, orders its requirements and publishes it", async ({
  page,
}) => {
  await newAdmin(page, uniqueEmail("jobs"), "Jobs E2E", "Ana Pérez")

  await page.getByRole("link", { name: "Jobs", exact: true }).click()
  await expect(page.getByRole("heading", { name: "No jobs yet" })).toBeVisible()
  await page.getByRole("link", { name: "New job" }).first().click()

  await page.getByLabel("Job title").fill("Platform Engineer")
  await page.getByLabel("Location").fill("Guadalajara, Jal.")

  // Publishing needs a must-have: try first, then add the requirements.
  await page.getByRole("button", { name: "Publish" }).click()
  await expect(
    page.getByText("Add at least one must-have requirement before publishing.")
  ).toBeVisible()

  const newRequirement = page.getByRole("textbox", { name: "New requirement" })
  await newRequirement.fill("Terraform")
  await page
    .getByRole("group", { name: "Kind of requirement 1" })
    .getByRole("button", { name: "Nice-to-have" })
    .click()
  await newRequirement.press("Enter")
  await newRequirement.fill("Go in production")
  await page
    .getByRole("group", { name: "Kind of requirement 2" })
    .getByRole("button", { name: "Must-have" })
    .click()
  await newRequirement.press("Enter")

  // Reorder with the keyboard alone: Space picks up, arrows move, Space drops.
  const handle = page.getByRole("button", {
    name: "Reorder: Requirement 2: Go in production",
  })
  await handle.focus()
  // dnd-kit measures the list between frames; a person never types this fast.
  for (const key of ["Space", "ArrowUp", "Space"]) {
    await page.keyboard.press(key)
    await page.waitForTimeout(250)
  }
  await expect(
    page.getByRole("textbox", { name: "Requirement 1", exact: true })
  ).toHaveValue("Go in production")

  await page.getByRole("button", { name: "Publish" }).click()
  await expect(page.getByText("Open", { exact: true })).toBeVisible()
  await expect(page.getByText("Changes saved.")).toBeVisible()

  await page.getByRole("link", { name: "Jobs", exact: true }).first().click()
  const row = page.getByRole("link", { name: /Platform Engineer/ })
  await expect(row).toContainText("1 must-have")
  await expect(row).toContainText("1 nice-to-have")
  await expect(row).toContainText("Open")
})
