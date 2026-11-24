import { expect, test } from "@playwright/test"

import { logIn, PASSWORD, signUp, verify } from "./helpers.ts"
import { appLink, uniqueEmail, waitForEmail } from "./mailpit.ts"

test("sign up, confirm the email, log in, stay logged in, log out", async ({
  page,
}) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  const email = uniqueEmail("signup")

  await signUp(page, email)

  // Not verified yet: login explains why.
  await logIn(page, email)
  await expect(
    page.getByText("Confirm your email before logging in")
  ).toBeVisible()

  await verify(page, email)
  await page.getByRole("link", { name: "Log in" }).click()
  await logIn(page, email)

  await expect(
    page.getByRole("heading", { name: "Welcome, Ana" })
  ).toBeVisible()
  await expect(page.getByText("You're in Acme E2E")).toBeVisible()

  // The refresh cookie restores the session after a reload; the access token never touches storage.
  await page.reload()
  await expect(
    page.getByRole("heading", { name: "Welcome, Ana" })
  ).toBeVisible()
  const stored = await page.evaluate(() =>
    JSON.stringify({ ...localStorage, ...sessionStorage })
  )
  expect(stored).not.toContain("eyJ")
  const cookies = await page.context().cookies()
  expect(
    cookies.find((cookie) => cookie.name === "terna_refresh")
  ).toMatchObject({
    httpOnly: true,
    sameSite: "Strict",
  })
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "terna_refresh"
  )

  await page.getByRole("button", { name: "Account menu" }).click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await expect(
    page.getByRole("heading", { name: "Log in to Terna" })
  ).toBeVisible()

  // Signed out for real: the home page sends you back to log in.
  await page.goto("/")
  await expect(page).toHaveURL(/\/login\?next=%2F$/)

  expect(errors).toEqual([])
})

test("recover a forgotten password", async ({ page }) => {
  const email = uniqueEmail("reset")
  await signUp(page, email)
  await verify(page, email)

  await page.goto("/login")
  await page.getByRole("link", { name: "Forgot password?" }).click()
  // Client-side navigation: wait for the new page, or the login form's field gets filled.
  await expect(
    page.getByRole("heading", { name: "Reset your password" })
  ).toBeVisible()
  await page.getByLabel("Email").fill(email)
  await page.getByRole("button", { name: "Send reset link" }).click()
  await expect(
    page.getByRole("heading", { name: "Check your inbox" })
  ).toBeVisible()

  const message = await waitForEmail(email, /Reset your Terna password/)
  const link = appLink(message.text, "/reset-password")
  const newPassword = "e2e-a-brand-new-passphrase-9"
  await page.goto(link)
  await page.getByLabel("New password", { exact: true }).fill(newPassword)
  await page.getByLabel("Confirm new password").fill(newPassword)
  await page.getByRole("button", { name: "Update password" }).click()
  await expect(
    page.getByRole("heading", { name: "Password updated" })
  ).toBeVisible()

  // The link works once.
  await page.goto(link)
  await page
    .getByLabel("New password", { exact: true })
    .fill("e2e-yet-another-passphrase-3")
  await page
    .getByLabel("Confirm new password")
    .fill("e2e-yet-another-passphrase-3")
  await page.getByRole("button", { name: "Update password" }).click()
  await expect(
    page.getByRole("heading", { name: "This reset link doesn't work" })
  ).toBeVisible()

  await logIn(page, email, PASSWORD)
  await expect(page.getByText("Email or password is incorrect.")).toBeVisible()
  await logIn(page, email, newPassword)
  await expect(
    page.getByRole("heading", { name: "Welcome, Ana" })
  ).toBeVisible()
})

test("signing in again with the same address reveals nothing", async ({
  page,
}) => {
  const email = uniqueEmail("dup")
  await signUp(page, email)
  // The second attempt looks exactly like the first; the owner gets a heads-up instead.
  await signUp(page, email)
  const message = await waitForEmail(email, /You already have a Terna account/)
  expect(message.text).toContain("/forgot-password")
})
