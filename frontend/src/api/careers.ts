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

export type ApplyForm = Schemas["ApplyForm"]
export type ApplyInput = Schemas["ApplyRequest"]

/** A fresh form token each visit: it times how long the form was open. */
export const applyFormQuery = (slug: string, id: string) =>
  queryOptions({
    queryKey: ["careers", slug, "job", id, "apply-form"],
    queryFn: () =>
      unwrap(
        api.GET("/api/careers/{slug}/jobs/{id}/apply/", {
          params: { path: { slug, id } },
        })
      ),
    staleTime: Infinity,
    gcTime: 0,
    retry,
  })

export function requestUpload(
  slug: string,
  id: string,
  body: Schemas["UploadRequestRequest"]
) {
  return unwrap(
    api.POST("/api/careers/{slug}/jobs/{id}/uploads/", {
      params: { path: { slug, id } },
      body,
    })
  )
}

export class UploadFailedError extends Error {}

/** PUTs the file straight to storage, reporting progress from 0 to 100. */
export function uploadFile(
  url: string,
  headers: Record<string, string>,
  file: File,
  onProgress: (percent: number) => void
) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open("PUT", url)
    for (const [name, value] of Object.entries(headers)) {
      request.setRequestHeader(name, value)
    }
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    request.onload = () =>
      request.status >= 200 && request.status < 300
        ? resolve()
        : reject(new UploadFailedError(`HTTP ${request.status}`))
    request.onerror = () => reject(new UploadFailedError("network"))
    request.send(file)
  })
}

export function submitApplication(slug: string, id: string, body: ApplyInput) {
  return unwrap(
    api.POST("/api/careers/{slug}/jobs/{id}/apply/", {
      params: { path: { slug, id } },
      body,
    })
  )
}
