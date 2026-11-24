import { queryOptions } from "@tanstack/react-query"

import { api, type Schemas } from "./client"

export type Health = Schemas["Health"]
export type ServiceName = "database" | "redis" | "storage"

export class ApiUnreachableError extends Error {
  constructor(status: number) {
    super(`Health endpoint answered ${status} without a health report`)
    this.name = "ApiUnreachableError"
  }
}

function isHealth(body: unknown): body is Health {
  return typeof body === "object" && body !== null && "checks" in body
}

export const healthQuery = queryOptions({
  queryKey: ["health"],
  queryFn: async ({ signal }) => {
    // 503 still carries a report: it means a dependency is down, not the API.
    const { data, error, response } = await api.GET("/api/health/", { signal })
    const body: unknown = data ?? error
    if (!isHealth(body)) {
      throw new ApiUnreachableError(response.status)
    }
    return body
  },
  refetchInterval: 30_000,
})
