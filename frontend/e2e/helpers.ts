import { expect, type Page } from "@playwright/test"

import { appLink, waitForEmail } from "./mailpit.ts"

export const PASSWORD = "e2e-correct-horse-battery-7"

export async function signUp(
  page: Page,
  email: string,
  { company = "Acme E2E", name = "Ana Pérez" } = {}
) {
  await page.goto("/signup")
  await page.getByLabel("Company name").fill(company)
  await page.getByLabel("Your full name").fill(name)
  await page.getByLabel("Work email").fill(email)
  await page.getByLabel("Password").fill(PASSWORD)
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(
    page.getByRole("heading", { name: "Check your inbox" })
  ).toBeVisible()
}

export async function verify(page: Page, email: string) {
  const message = await waitForEmail(email, /Verify your email/)
  await page.goto(appLink(message.text, "/verify-email"))
  await expect(
    page.getByRole("heading", { name: "Email confirmed" })
  ).toBeVisible()
}

export async function logIn(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: "Log in" }).click()
}

/** Sign up, confirm the address and log in: ready on the home page. */
export async function newAdmin(
  page: Page,
  email: string,
  company: string,
  name: string
) {
  await signUp(page, email, { company, name })
  await verify(page, email)
  await logIn(page, email)
  await expect(
    page.getByRole("heading", { name: `Welcome, ${name.split(" ")[0]}` })
  ).toBeVisible()
}
