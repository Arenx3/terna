import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type Profile = Schemas["Profile"]
export type TimelineEvent = Schemas["TimelineEvent"]
export type CandidateComment = Schemas["Comment"]
export type Teammate = Schemas["Teammate"]
export type Inbox = Schemas["Inbox"]
export type AppNotification = Schemas["Notification"]

type Result<T> = { data?: T; error?: unknown; response: Response }

async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

const path = (id: number) => ({ params: { path: { id } } })

export const profileQuery = (companyId: string, id: number) =>
  queryOptions({
    queryKey: ["applications", companyId, id, "profile"],
    queryFn: () => unwrap(api.GET("/api/applications/{id}/", path(id))),
  })

export const timelineQuery = (companyId: string, id: number) =>
  queryOptions({
    queryKey: ["applications", companyId, id, "timeline"],
    queryFn: () =>
      unwrap(api.GET("/api/applications/{id}/timeline/", path(id))),
  })

export const commentsQuery = (companyId: string, id: number) =>
  queryOptions({
    queryKey: ["applications", companyId, id, "comments"],
    queryFn: () =>
      unwrap(api.GET("/api/applications/{id}/comments/", path(id))),
  })

export function postComment(id: number, body: string, mentions: string[]) {
  return unwrap(
    api.POST("/api/applications/{id}/comments/", {
      ...path(id),
      body: { body, mentions },
    })
  )
}

export function setInterviewers(id: number, users: string[]) {
  return unwrap(
    api.PUT("/api/applications/{id}/interviewers/", {
      ...path(id),
      body: { users },
    })
  )
}

/** A five-minute link straight to storage, to show in the browser or download. */
export async function resumeUrl(id: number, inline: boolean) {
  const data = await unwrap(
    api.GET("/api/applications/{id}/resume/", {
      params: { path: { id }, query: { inline } },
    })
  )
  return data.url
}

export const inboxQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["notifications", companyId],
    queryFn: () => unwrap(api.GET("/api/notifications/")),
    refetchInterval: 30_000,
  })

export function markRead(ids: number[] = []) {
  return unwrap(api.POST("/api/notifications/read/", { body: { ids } }))
}
