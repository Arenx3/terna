import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"
import { currentLanguage } from "@/i18n"

import { sessionStore } from "./session"

type Result<T> = { data?: T; error?: unknown; response: Response }

/** The data of a successful call, or an ApiError carrying the code and field errors. */
async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

export async function login(email: string, password: string) {
  const session = await unwrap(
    api.POST("/api/auth/login/", { body: { email, password } })
  )
  sessionStore.set(session)
  return session
}

export async function logout() {
  try {
    await api.POST("/api/auth/logout/")
  } finally {
    sessionStore.set(null)
  }
}

export function signup(body: Omit<Schemas["Signup"], "language">) {
  return unwrap(
    api.POST("/api/auth/signup/", {
      body: { ...body, language: currentLanguage() },
    })
  )
}

export function verifyEmail(token: string) {
  return unwrap(api.POST("/api/auth/verify-email/", { body: { token } }))
}

export function resendVerification(email: string) {
  return unwrap(api.POST("/api/auth/verify-email/resend/", { body: { email } }))
}

export function requestPasswordReset(email: string) {
  return unwrap(api.POST("/api/auth/password-reset/", { body: { email } }))
}

export function confirmPasswordReset(body: Schemas["PasswordResetConfirm"]) {
  return unwrap(api.POST("/api/auth/password-reset/confirm/", { body }))
}
