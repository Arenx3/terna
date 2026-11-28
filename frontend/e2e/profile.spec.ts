import { expect, test, type Browser, type Page } from "@playwright/test"

import {
  applyAs,
  careersPathOf,
  createJob,
  expectNoAccessibilityViolations,
  newAdmin,
  PASSWORD,
} from "./helpers.ts"
import { appLink, uniqueEmail, waitForEmail } from "./mailpit.ts"

/** Invite an interviewer and accept in their own browser; returns their page. */
async function addInterviewer(page: Page, browser: Browser, company: string) {
  const email = uniqueEmail("interviewer")
  await page.goto("/team")
  await page.getByLabel("Email", { exact: true }).fill(email)
  await page.getByRole("combobox", { name: "Role", exact: true }).click()
  await page.getByRole("option", { name: "Interviewer" }).click()
  await page.getByRole("button", { name: "Send invitation" }).click()
  const message = await waitForEmail(
    email,
    new RegExp(`invited you to ${company}`)
  )
  const context = await browser.newContext({ locale: "en-US" })
  const interviewer = await context.newPage()
  await interviewer.goto(appLink(message.text, "/invitations/accept"))
  await interviewer.getByLabel("Your full name").fill("Diego Ramos")
  await interviewer.getByLabel("Password").fill(PASSWORD)
  await interviewer.getByRole("button", { name: "Accept and join" }).click()
  await expect(
    interviewer.getByRole("heading", { name: "Welcome, Diego" })
  ).toBeVisible()
  return interviewer
}

test("the team opens a candidate, assigns an interviewer and talks about them", async ({
  page,
  browser,
}) => {
  await newAdmin(page, uniqueEmail("profile"), "Profile E2E", "Ana Pérez")
  const jobId = await createJob(page, "Data Engineer", true)
  const careersPath = await careersPathOf(page)
  await applyAs(browser, `${careersPath}/jobs/${jobId}`, {
    name: "Lucía Torres",
    email: uniqueEmail("lucia"),
  })
  const interviewer = await addInterviewer(page, browser, "Profile E2E")

  // From the board, the profile opens over it, with an address of its own.
  await page.goto(`/jobs/${jobId}/candidates`)
  await page.getByRole("link", { name: "Lucía Torres" }).click()
  const panel = page.getByRole("dialog", { name: "Lucía Torres" })
  await expect(panel).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`/jobs/${jobId}/candidates/\\d+$`))
  const profileUrl = page.url()
  // It opens on the screening; the team's activity is the next tab.
  await expect(panel.getByRole("tab", { name: "Screening" })).toHaveAttribute(
    "aria-selected",
    "true"
  )
  await panel.getByRole("tab", { name: "Activity" }).click()
  await expect(panel.getByText("Applied to Data Engineer")).toBeVisible()
  await expectNoAccessibilityViolations(page)

  // The interviewer can't open someone they aren't assigned to.
  const applicationId = profileUrl.split("/").at(-1)
  await interviewer.goto(`/applications/${applicationId}`)
  await expect(
    interviewer.getByText(
      "This candidate doesn't exist, or you don't have access to them."
    )
  ).toBeVisible()

  await panel.getByRole("button", { name: "Assign interviewers" }).click()
  const diego = page.getByRole("menuitemcheckbox", { name: "Diego Ramos" })
  await diego.click()
  // Saved and reloaded: the item turns checked only once the profile says so.
  await expect(diego).toBeChecked()
  await page.keyboard.press("Escape")
  await expect(diego).toBeHidden()
  await expect(panel.getByText("Diego Ramos", { exact: true })).toBeVisible()

  // A comment that mentions Diego, chosen from the suggestions with the keyboard.
  const box = panel.getByRole("combobox", { name: "Comment for your team" })
  await box.pressSequentially("Strong on Spark. @Die")
  await expect(page.getByRole("option", { name: /Diego Ramos/ })).toBeVisible()
  await box.press("Enter")
  // The suggestion went in as a full name, ready to keep typing.
  await expect(box).toHaveValue("Strong on Spark. @Diego Ramos ")
  await box.pressSequentially("can you take the technical interview?")
  await panel.getByRole("button", { name: "Comment", exact: true }).click()
  await expect(
    panel.getByText("can you take the technical interview?")
  ).toBeVisible()

  // Diego hears about both, and can now open the candidate.
  // The inbox refreshes on its own every half minute; no reloading needed.
  await interviewer.goto("/")
  const bell = interviewer.getByRole("button", {
    name: /Notifications: 2 unread/,
  })
  await expect(bell).toBeVisible({ timeout: 35_000 })
  await bell.click()
  await interviewer
    .getByRole("menuitem", { name: /Ana Pérez mentioned you on Lucía Torres/ })
    .click()
  await expect(
    interviewer.getByRole("heading", { level: 1, name: "Lucía Torres" })
  ).toBeVisible()
  await expect(
    interviewer.getByText("can you take the technical interview?")
  ).toBeVisible()
  await interviewer.context().close()

  // Closing the panel goes back to the board.
  await page.keyboard.press("Escape")
  await expect(page).toHaveURL(new RegExp(`/jobs/${jobId}/candidates$`))
})
