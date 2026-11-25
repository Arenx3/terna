import { expect, test, type Page } from "@playwright/test"

import {
  applyAs,
  careersPathOf,
  createJob,
  expectNoAccessibilityViolations,
  logIn,
  newAdmin,
} from "./helpers.ts"
import { uniqueEmail } from "./mailpit.ts"

/** Move a card with the keyboard alone: focus its menu, pick the stage, confirm. */
async function moveWithKeyboard(page: Page, name: string, stage: string) {
  await page.getByRole("button", { name: `Actions for ${name}` }).focus()
  await page.keyboard.press("Enter")
  const item = page.getByRole("menuitem", { name: stage, exact: true })
  await expect(item).toBeVisible()
  await item.focus()
  await page.keyboard.press("Enter")
}

test("two people on one board see each other's moves live", async ({
  page,
  browser,
}) => {
  const email = uniqueEmail("board")
  await newAdmin(page, email, "Board E2E", "Ana Pérez")
  const jobId = await createJob(page, "Site Reliability Engineer", true)
  const careersPath = await careersPathOf(page)
  await applyAs(browser, `${careersPath}/jobs/${jobId}`, {
    name: "Lucía Torres",
    email: uniqueEmail("lucia"),
  })

  // The same admin on a second computer.
  const otherContext = await browser.newContext({ locale: "en-US" })
  const other = await otherContext.newPage()
  await logIn(other, email)
  await expect(other.getByRole("heading", { name: /Welcome/ })).toBeVisible()

  for (const board of [page, other]) {
    await board.goto(`/jobs/${jobId}/candidates`)
    await expect(board.getByText("Live", { exact: true })).toBeVisible()
  }
  await expect(page.getByRole("region", { name: /^Applied/ })).toContainText(
    "Lucía Torres"
  )
  await expectNoAccessibilityViolations(page)

  const started = Date.now()
  await moveWithKeyboard(page, "Lucía Torres", "Interview")
  await expect(other.getByRole("region", { name: /^Interview/ })).toContainText(
    "Lucía Torres",
    { timeout: 3_000 }
  )
  console.log(
    `Live move seen by the other session after ${Date.now() - started} ms`
  )
  await expect(
    other.getByRole("region", { name: /^Applied/ })
  ).not.toContainText("Lucía Torres")

  // Rejecting asks why, still without a mouse.
  await moveWithKeyboard(page, "Lucía Torres", "Rejected")
  const dialog = page.getByRole("alertdialog", { name: "Reject Lucía Torres?" })
  await expect(dialog).toBeVisible()
  await dialog.getByRole("radio", { name: "Withdrew" }).check()
  await dialog.getByRole("button", { name: "Reject" }).press("Enter")
  await expect(other.getByRole("region", { name: /^Rejected/ })).toContainText(
    "Withdrew",
    { timeout: 3_000 }
  )

  // Every move is on the record.
  await page.goto("/settings/audit")
  await expect(
    page
      .getByRole("listitem")
      .filter({ hasText: "Ana Pérez moved Lucía Torres to Rejected" })
  ).toBeVisible({ timeout: 10_000 })
  await otherContext.close()
})
