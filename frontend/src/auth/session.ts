import { useSyncExternalStore } from "react"

import type { Schemas } from "@/api/client"

export type Session = Schemas["Session"]
export type SessionStatus = "loading" | "authenticated" | "anonymous"

/**
 * The signed-in session. The access token lives only in memory; the refresh
 * token is an httpOnly cookie the browser sends to /api/auth/ by itself, so a
 * reload restores the session without JavaScript ever touching it.
 */
let session: Session | null = null
let status: SessionStatus = "loading"
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export const sessionStore = {
  get: () => session,
  status: () => status,
  set(next: Session | null) {
    session = next
    status = next ? "authenticated" : "anonymous"
    emit()
  },
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}

export function useSession() {
  const current = useSyncExternalStore(sessionStore.subscribe, sessionStore.get)
  const currentStatus = useSyncExternalStore(
    sessionStore.subscribe,
    sessionStore.status
  )
  return { session: current, status: currentStatus }
}

let refreshing: Promise<Session | null> | null = null

/** Exchanges the refresh cookie for a new session. Concurrent callers share one request. */
export function refreshSession(): Promise<Session | null> {
  refreshing ??= fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  })
    .then(async (response) => {
      // 200 carries a session; 204 means nobody is signed in; 401 means it expired.
      const next =
        response.status === 200 ? ((await response.json()) as Session) : null
      sessionStore.set(next)
      return next
    })
    .catch(() => {
      sessionStore.set(null)
      return null
    })
    .finally(() => {
      refreshing = null
    })
  return refreshing
}
