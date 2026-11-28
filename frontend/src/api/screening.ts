import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type ResumeText = Schemas["ResumeText"]
export type Passage = Schemas["Passage"]
export type Section = Schemas["SectionEnum"]
export type RedactionKind = Schemas["RedactionKindEnum"]
export type ExtractionStatus = Schemas["ExtractionStatusEnum"]
export type ExtractionReason = Schemas["ExtractionReasonEnum"]

export type Screening = Schemas["Screening"]
export type ScreeningSummary = Schemas["ScreeningSummary"]
export type ScreeningStatus = Schemas["ScreeningStatusEnum"]
export type RequirementResult = Schemas["RequirementResult"]
export type Evidence = Schemas["Evidence"]
export type Verdict = Schemas["VerdictEnum"]
export type Signal = Schemas["SignalEnum"]
export type DictionaryEntry = Schemas["Entry"]
export type DictionaryInput = Schemas["EntryRequest"]

type Result<T> = { data?: T; error?: unknown; response: Response }

async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

const path = (id: number) => ({ params: { path: { id } } })

export const isReading = (status: ExtractionStatus) =>
  status === "pending" || status === "processing"

/** The résumé as the screening reads it. Checks back every 2 s while a worker reads it. */
export const resumeTextQuery = (companyId: string, id: number) =>
  queryOptions({
    queryKey: ["applications", companyId, id, "resume-text"],
    queryFn: () =>
      unwrap(api.GET("/api/applications/{id}/resume/text/", path(id))),
    refetchInterval: (query) =>
      query.state.data && isReading(query.state.data.status) ? 2000 : false,
  })

export function reprocessResume(id: number) {
  return unwrap(api.POST("/api/applications/{id}/resume/reprocess/", path(id)))
}

/** Still working on it: the résumé is being read, or the requirements compared. */
export function isScreening(
  screening: Pick<Screening, "status" | "resume_status">
) {
  if (screening.status === "pending" || screening.status === "processing")
    return true
  return (
    screening.status === "waiting" &&
    screening.resume_status !== null &&
    isReading(screening.resume_status)
  )
}

/**
 * Every requirement with its verdict and evidence. Checks back every 2 s while the
 * worker is on it; the board's live channel also refreshes it when it finishes.
 */
export const screeningQuery = (companyId: string, id: number) =>
  queryOptions({
    queryKey: ["applications", companyId, id, "screening"],
    queryFn: () =>
      unwrap(api.GET("/api/applications/{id}/screening/", path(id))),
    refetchInterval: (query) =>
      query.state.data && isScreening(query.state.data) ? 2000 : false,
  })

export function rerunScreening(id: number) {
  return unwrap(api.POST("/api/applications/{id}/screening/rerun/", path(id)))
}

export const dictionaryQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["screening-dictionary", companyId],
    queryFn: () => unwrap(api.GET("/api/screening/dictionary/")),
  })

export function addEntry(body: DictionaryInput) {
  return unwrap(api.POST("/api/screening/dictionary/", { body }))
}

export function saveEntry(id: number, body: DictionaryInput) {
  return unwrap(
    api.PUT("/api/screening/dictionary/{id}/", { ...path(id), body })
  )
}

export function deleteEntry(id: number) {
  return unwrap(api.DELETE("/api/screening/dictionary/{id}/", path(id)))
}
