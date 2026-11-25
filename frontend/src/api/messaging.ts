import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type EmailTemplate = Schemas["Template"]
export type TemplateKind = Schemas["TemplateKindEnum"]
export type CandidateEmail = Schemas["EmailMessage"]
export type EmailDraft = Schemas["Draft"]
export type NewEmail = Schemas["NewEmailRequest"]

export const TEMPLATE_KINDS: TemplateKind[] = [
  "application_received",
  "stage_advanced",
  "rejection",
  "interview_invitation",
]

type Result<T> = { data?: T; error?: unknown; response: Response }

async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

export const templatesQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["email-templates", companyId],
    queryFn: () => unwrap(api.GET("/api/email-templates/")),
  })

export function saveTemplate(
  kind: TemplateKind,
  language: string,
  body: { subject: string; body: string }
) {
  return unwrap(
    api.PUT("/api/email-templates/{kind}/{language}/", {
      params: { path: { kind, language } },
      body,
    })
  )
}

export function resetTemplate(kind: TemplateKind, language: string) {
  return unwrap(
    api.DELETE("/api/email-templates/{kind}/{language}/", {
      params: { path: { kind, language } },
    })
  )
}

export const candidateEmailsQuery = (
  companyId: string,
  applicationId: number
) =>
  queryOptions({
    queryKey: ["applications", companyId, applicationId, "emails"],
    queryFn: () =>
      unwrap(
        api.GET("/api/applications/{id}/emails/", {
          params: { path: { id: applicationId } },
        })
      ),
  })

export function emailDraft(applicationId: number, kind: TemplateKind) {
  return unwrap(
    api.GET("/api/applications/{id}/emails/draft/", {
      params: { path: { id: applicationId }, query: { kind } },
    })
  )
}

export function sendEmail(applicationId: number, body: NewEmail) {
  return unwrap(
    api.POST("/api/applications/{id}/emails/", {
      params: { path: { id: applicationId } },
      body,
    })
  )
}

export function retryEmail(id: number) {
  return unwrap(
    api.POST("/api/emails/{id}/retry/", { params: { path: { id } } })
  )
}

export function cancelEmail(id: number) {
  return unwrap(
    api.POST("/api/emails/{id}/cancel/", { params: { path: { id } } })
  )
}

/** A safe, local renderer for previews: the same `{{ variable }}` syntax the API uses. */
export function renderTemplate(text: string, values: Record<string, string>) {
  return text.replace(/\{\{\s*([^{}]*?)\s*\}\}/g, (match, name: string) =>
    name in values ? values[name] : match
  )
}

/** Variables the text uses that this kind of email doesn't offer. */
export function unknownVariables(text: string, allowed: string[]) {
  const found = [...text.matchAll(/\{\{\s*([^{}]*?)\s*\}\}/g)].map((m) => m[1])
  return [...new Set(found.filter((name) => !allowed.includes(name)))]
}

/** When a scheduled email goes out: tomorrow or in a few days, at 9:00 local time. */
export function nineAmIn(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  date.setHours(9, 0, 0, 0)
  return date.toISOString()
}
