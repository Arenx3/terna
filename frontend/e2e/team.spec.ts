import { expect, test } from "@playwright/test"

import { newAdmin, PASSWORD } from "./helpers.ts"
import { appLink, uniqueEmail, waitForEmail } from "./mailpit.ts"

test("an admin invites a teammate, who joins with a new account and cannot manage the team", async ({
  browser,
  page,
}) => {
  const adminEmail = uniqueEmail("admin")
  const inviteeEmail = uniqueEmail("invitee")
  await newAdmin(page, adminEmail, "Acme Team", "Ana Pérez")

  await page.getByRole("link", { name: "Team" }).click()
  await expect(
    page.getByRole("heading", { name: "Invite someone" })
  ).toBeVisible()
  await page.getByLabel("Email", { exact: true }).fill(inviteeEmail)
  await page.getByRole("combobox", { name: "Role", exact: true }).click()
  await page.getByRole("option", { name: "Interviewer" }).click()
  await page.getByRole("button", { name: "Send invitation" }).click()
  await expect(
    page.getByText(`Invitation sent to ${inviteeEmail}.`)
  ).toBeVisible()
  // Listed as pending (exact: the confirmation message also mentions the address).
  await expect(page.getByText(inviteeEmail, { exact: true })).toBeVisible()

  // The invitee opens the email in their own browser.
  const message = await waitForEmail(inviteeEmail, /invited you to Acme Team/)
  expect(message.text).toContain("as interviewer")
  const invitee = await browser.newPage()
  await invitee.goto(appLink(message.text, "/invitations/accept"))
  await expect(
    invitee.getByRole("heading", { name: "Join Acme Team" })
  ).toBeVisible()
  await invitee.getByLabel("Your full name").fill("Ines Torres")
  await invitee.getByLabel("Password").fill(PASSWORD)
  await invitee.getByRole("button", { name: "Accept and join" }).click()
  await expect(
    invitee.getByRole("heading", { name: "Welcome, Ines" })
  ).toBeVisible()
  await expect(invitee.getByText("You're in Acme Team")).toBeVisible()

  // An interviewer sees the team, but none of the admin controls.
  await invitee.getByRole("link", { name: "Team" }).click()
  await expect(invitee.getByText("Only admins can invite people")).toBeVisible()
  await expect(
    invitee.getByRole("heading", { name: "Invite someone" })
  ).toHaveCount(0)
  await expect(invitee.getByRole("button", { name: /^Remove/ })).toHaveCount(0)

  // The link works once.
  await invitee.goto(appLink(message.text, "/invitations/accept"))
  await expect(
    invitee.getByRole("heading", { name: "This invitation doesn't work" })
  ).toBeVisible()

  // Back in the admin's browser: Ines is a member, and the invitation is no longer pending.
  await page.reload()
  await expect(page.getByRole("row", { name: /Ines Torres/ })).toBeVisible()
  await expect(page.getByText("No pending invitations.")).toBeVisible()
  await page.getByRole("combobox", { name: "Role for Ines Torres" }).click()
  await page.getByRole("option", { name: "Recruiter" }).click()
  await expect(
    page.getByRole("combobox", { name: "Role for Ines Torres" })
  ).toHaveText(/Recruiter/)
  await invitee.close()
})

test("someone in two companies switches between them", async ({
  browser,
  page,
}) => {
  const alphaEmail = uniqueEmail("alpha")
  const betaEmail = uniqueEmail("beta")
  await newAdmin(page, alphaEmail, "Alpha Corp", "Ana Pérez")

  // Beta's admin invites Ana.
  const beta = await browser.newPage()
  await newAdmin(beta, betaEmail, "Beta Corp", "Bruno Díaz")
  await beta.getByRole("link", { name: "Team" }).click()
  await beta.getByLabel("Email", { exact: true }).fill(alphaEmail)
  await beta.getByRole("button", { name: "Send invitation" }).click()
  await expect(
    beta.getByText(`Invitation sent to ${alphaEmail}.`)
  ).toBeVisible()
  await beta.close()

  // Ana, already signed in to Alpha, accepts with one click.
  const message = await waitForEmail(alphaEmail, /invited you to Beta Corp/)
  await page.goto(appLink(message.text, "/invitations/accept"))
  await page.getByRole("button", { name: "Join Beta Corp" }).click()
  await expect(page.getByText("You're in Beta Corp")).toBeVisible()

  // Switching company switches everything shown.
  await page.getByRole("button", { name: "Switch company" }).click()
  await page.getByRole("menuitemradio", { name: "Alpha Corp" }).click()
  await expect(page.getByText("You're in Alpha Corp")).toBeVisible()
  await page.getByRole("link", { name: "Team" }).click()
  await expect(page.getByRole("row", { name: /Ana Pérez/ })).toBeVisible()
  await expect(page.getByRole("row", { name: /Bruno Díaz/ })).toHaveCount(0)

  await page.getByRole("button", { name: "Switch company" }).click()
  await page.getByRole("menuitemradio", { name: "Beta Corp" }).click()
  await expect(page.getByText("You're in Beta Corp")).toBeVisible()
  await page.getByRole("link", { name: "Team" }).click()
  await expect(page.getByRole("row", { name: /Bruno Díaz/ })).toBeVisible()
  // In Beta, Ana is a recruiter: no admin controls.
  await expect(
    page.getByRole("heading", { name: "Invite someone" })
  ).toHaveCount(0)
})
