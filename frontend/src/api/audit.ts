import { infiniteQueryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "@/api/client"
import { ApiError } from "@/api/errors"

export type AuditEvent = Schemas["AuditEvent"]
export type EventType = Schemas["EventTypeEnum"]

/** Areas of activity, the coarse filter: each event type starts with one. */
export const AUDIT_AREAS = [
  "job",
  "application",
  "member",
  "invitation",
] as const
export type AuditArea = (typeof AUDIT_AREAS)[number]

export type AuditFilters = {
  area?: AuditArea
  actor?: string
  /** ISO instants: start inclusive, end exclusive. */
  since?: string
  until?: string
}

const PAGE_SIZE = 50

// Keyed by company: switching companies must never show the previous one's log.
export const auditQuery = (companyId: string, filters: AuditFilters) =>
  infiniteQueryOptions({
    queryKey: ["audit", companyId, filters],
    initialPageParam: undefined as number | undefined,
    queryFn: async ({ pageParam }) => {
      const { data, error, response } = await api.GET("/api/audit/", {
        params: {
          query: {
            type: filters.area,
            actor: filters.actor,
            since: filters.since,
            until: filters.until,
            before: pageParam,
            limit: PAGE_SIZE,
          },
        },
      })
      if (!response.ok || !data) throw new ApiError(response.status, error)
      return data
    },
    getNextPageParam: (page) => page.next_before ?? undefined,
  })
