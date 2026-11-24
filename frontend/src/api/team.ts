import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type Member = Schemas["Member"]
export type Invitation = Schemas["Invitation"]
export type Role = Schemas["RoleEnum"]

export const ROLES: Role[] = [
  "admin",
  "recruiter",
  "hiring_manager",
  "interviewer",
]

type Result<T> = { data?: T; error?: unknown; response: Response }

async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}

// Keyed by company: switching companies must never show the previous one's team.
export const membersQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["team", companyId, "members"],
    queryFn: () => unwrap(api.GET("/api/team/members/")),
  })

export const invitationsQuery = (companyId: string) =>
  queryOptions({
    queryKey: ["team", companyId, "invitations"],
    queryFn: () => unwrap(api.GET("/api/team/invitations/")),
  })

export function invite(email: string, role: Role) {
  return unwrap(api.POST("/api/team/invitations/", { body: { email, role } }))
}

export function revokeInvitation(id: number) {
  return unwrap(
    api.DELETE("/api/team/invitations/{id}/", { params: { path: { id } } })
  )
}

export function changeRole(id: number, role: Role) {
  return unwrap(
    api.PATCH("/api/team/members/{id}/", {
      params: { path: { id } },
      body: { role },
    })
  )
}

export function removeMember(id: number) {
  return unwrap(
    api.DELETE("/api/team/members/{id}/", { params: { path: { id } } })
  )
}
