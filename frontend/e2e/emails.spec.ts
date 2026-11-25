import { expect, test } from "@playwright/test"

import {
  applyAs,
  careersPathOf,
  createJob,
  expectNoAccessibilityViolations,
  newAdmin,
} from "./helpers.ts"
import { uniqueEmail, waitForEmail } from "./mailpit.ts"

test("the company writes its rejection email, and a rejected candidate gets it", async ({
  page,
  browser,
}) => {
  await newAdmin(page, uniqueEmail("emails"), "Emails E2E", "Ana Pérez")
  const jobId = await createJob(page, "Payroll Analyst", true)
  const candidate = uniqueEmail("lucia")
  await applyAs(browser, `${await careersPathOf(page)}/jobs/${jobId}`, {
    name: "Lucía Torres",
    email: candidate,
  })

  // The template: a variable that doesn't exist can't be saved.
  await page.goto("/settings/emails?kind=rejection")
  await page.getByRole("tab", { name: "English" }).click()
  const subject = page.getByRole("textbox", { name: "Subject" })
  const body = page.getByRole("textbox", { name: "Message" })
  await body.fill("Hi {{ candidate.first_name }}, {{ candidate.salary }}")
  await expect(
    page.getByText("These variables don't exist: candidate.salary")
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Save" })).toBeDisabled()
  await expectNoAccessibilityViolations(page)

  await subject.fill("About {{ job.title }}")
  await body.fill(
    "Hi {{ candidate.first_name }}, thank you for applying to {{ job.title }}. We went another way this time."
  )
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Saved.")).toBeVisible()

  // Rejecting from the board offers that email; send it right away.
  await page.goto(`/jobs/${jobId}/candidates`)
  await page.getByRole("button", { name: "Actions for Lucía Torres" }).click()
  await page.getByRole("menuitem", { name: "Rejected", exact: true }).click()
  const dialog = page.getByRole("alertdialog", { name: "Reject Lucía Torres?" })
  await expect(
    dialog.getByRole("checkbox", { name: /Also send the rejection email/ })
  ).toBeChecked()
  await dialog.getByRole("combobox", { name: "When" }).click()
  await page.getByRole("option", { name: "Now" }).click()
  await dialog.getByRole("button", { name: "Reject" }).click()

  const email = await waitForEmail(candidate, /About Payroll Analyst/)
  expect(email.text).toContain(
    "Hi Lucía, thank you for applying to Payroll Analyst. We went another way this time."
  )

  // And it's on the candidate's record.
  await page.getByRole("link", { name: "Lucía Torres" }).click()
  const panel = page.getByRole("dialog", { name: "Lucía Torres" })
  await panel.getByRole("tab", { name: "Emails" }).click()
  const sent = panel
    .getByRole("listitem")
    .filter({ hasText: "About Payroll Analyst" })
  await expect(async () => {
    await panel.getByRole("tab", { name: "Activity" }).click()
    await panel.getByRole("tab", { name: "Emails" }).click()
    await expect(sent).toContainText("Sent", { timeout: 2_000 })
  }).toPass({ timeout: 20_000 })
})
