import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type JobApplication = Schemas["Application"]

export const jobApplicationsQuery = (companyId: string, jobId: string) =>
  queryOptions({
    queryKey: ["jobs", companyId, "applications", jobId],
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/api/jobs/{id}/applications/",
        { params: { path: { id: jobId } } }
      )
      if (!response.ok || !data) throw new ApiError(response.status, error)
      return data
    },
  })

/** A short-lived link straight to storage; the file never passes through the API. */
export async function resumeLink(applicationId: number) {
  const { data, error, response } = await api.GET(
    "/api/applications/{id}/resume/",
    { params: { path: { id: applicationId } } }
  )
  if (!response.ok || !data) throw new ApiError(response.status, error)
  return data.url
}
