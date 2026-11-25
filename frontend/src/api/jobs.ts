import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type Job = Schemas["Job"]
export type JobSummary = Schemas["JobSummary"]
export type JobStatus = Schemas["JobStatusEnum"]
export type Requirement = Schemas["Requirement"]
export type RequirementKind = Schemas["RequirementKindEnum"]
export type Stage = Schemas["Stage"]
export type StageKind = Schemas["StageKindEnum"]
export type Workplace = Schemas["WorkplaceEnum"]
export type Employment = Schemas["EmploymentEnum"]
export type JobInput = Schemas["JobRequest"]
export type StageInput = Schemas["StageRequest"]

export const JOB_STATUSES: JobStatus[] = ["open", "draft", "closed"]
export const WORKPLACES: Workplace[] = ["onsite", "hybrid", "remote"]
export const EMPLOYMENTS: Employment[] = [
  "full_time",
  "part_time",
  "contract",
  "internship",
]
/** Kinds a recruiter can place between Applied and the Hired/Rejected ends. */
export const MIDDLE_STAGE_KINDS: StageKind[] = [
  "screening",
  "interview",
  "offer",
]

type Result<T> = { data?: T; error?: unknown; response: Response }

async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

// Keyed by company: switching companies must never show the previous one's jobs.
export const jobsQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["jobs", companyId, "list"],
    queryFn: () => unwrap(api.GET("/api/jobs/")),
  })

export const jobQuery = (companyId: string, id: string) =>
  queryOptions({
    queryKey: ["jobs", companyId, "detail", id],
    queryFn: () =>
      unwrap(api.GET("/api/jobs/{id}/", { params: { path: { id } } })),
  })

export const pipelineTemplateQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["jobs", companyId, "pipeline-template"],
    queryFn: () => unwrap(api.GET("/api/jobs/pipeline-template/")),
  })

export function createJob(body: JobInput) {
  return unwrap(api.POST("/api/jobs/", { body }))
}

export function updateJob(id: string, body: JobInput) {
  return unwrap(
    api.PATCH("/api/jobs/{id}/", { params: { path: { id } }, body })
  )
}

export function publishJob(id: string) {
  return unwrap(
    api.POST("/api/jobs/{id}/publish/", { params: { path: { id } } })
  )
}

export function closeJob(id: string) {
  return unwrap(api.POST("/api/jobs/{id}/close/", { params: { path: { id } } }))
}

export function deleteJob(id: string) {
  return unwrap(api.DELETE("/api/jobs/{id}/", { params: { path: { id } } }))
}

export function savePipelineTemplate(stages: StageInput[]) {
  return unwrap(api.PUT("/api/jobs/pipeline-template/", { body: { stages } }))
}
