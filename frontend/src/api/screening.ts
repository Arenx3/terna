import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type ResumeText = Schemas["ResumeText"]
export type Passage = Schemas["Passage"]
export type Section = Schemas["SectionEnum"]
export type RedactionKind = Schemas["RedactionKindEnum"]
export type ExtractionStatus = Schemas["ExtractionStatusEnum"]
export type ExtractionReason = Schemas["ExtractionReasonEnum"]

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
