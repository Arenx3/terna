import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type CareersPage = Schemas["CareersPage"]
export type PublicJobSummary = Schemas["PublicJobSummary"]
export type PublicJob = Schemas["PublicJob"]
export type CurrentCompany = Schemas["CurrentCompany"]

type Result<T> = { data?: T; error?: unknown; response: Response }

async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

// A missing page is an answer, not a hiccup: don't retry 404s.
const retry = (failures: number, error: unknown) =>
  !(error instanceof ApiError && error.status === 404) && failures < 2

export const careersQuery = (slug: string) =>
  queryOptions({
    queryKey: ["careers", slug],
    queryFn: () =>
      unwrap(api.GET("/api/careers/{slug}/", { params: { path: { slug } } })),
    retry,
  })

export const publicJobQuery = (slug: string, id: string) =>
  queryOptions({
    queryKey: ["careers", slug, "job", id],
    queryFn: () =>
      unwrap(
        api.GET("/api/careers/{slug}/jobs/{id}/", {
          params: { path: { slug, id } },
        })
      ),
    retry,
  })

/** The signed-in person's active company, with its careers page slug. */
export const currentCompanyQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["company", companyId],
    queryFn: () => unwrap(api.GET("/api/company/")),
    staleTime: 5 * 60_000,
  })
