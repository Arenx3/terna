import type { TFunction } from "i18next"

/** A failed API call, with field errors split out for forms. */
export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly fields: Record<string, string[]>

  constructor(status: number, body: unknown) {
    const data = (
      typeof body === "object" && body !== null ? body : {}
    ) as Record<string, unknown>
    super(typeof data.detail === "string" ? data.detail : `HTTP ${status}`)
    this.name = "ApiError"
    this.status = status
    this.code = typeof data.code === "string" ? data.code : undefined
    this.fields = Object.fromEntries(
      Object.entries(data)
        .filter(
          ([key, value]) =>
            key !== "detail" && key !== "code" && Array.isArray(value)
        )
        .map(([key, value]) => [key, (value as unknown[]).map(String)])
    )
  }
}

const KNOWN_CODES = [
  "invalid_credentials",
  "email_not_verified",
  "no_company",
  "invalid_link",
  "session_expired",
  "throttled",
] as const

type KnownCode = (typeof KNOWN_CODES)[number]

function isKnownCode(code: string | undefined): code is KnownCode {
  return KNOWN_CODES.some((known) => known === code)
}

/** One sentence for the person: our own copy for known codes, otherwise a generic one. */
export function errorMessage(t: TFunction, error: unknown): string {
  if (error instanceof ApiError) {
    if (isKnownCode(error.code)) return t(`errors.${error.code}`)
    if (error.status === 429) return t("errors.throttled")
    if (error.status >= 500) return t("errors.server")
    if (Object.keys(error.fields).length > 0) return t("errors.fields")
  }
  return t("errors.network")
}
