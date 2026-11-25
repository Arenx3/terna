import { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, Outlet, useLocation } from "react-router"

import { refreshSession, sessionStore, useSession } from "@/auth/session"
import { Skeleton } from "@/components/ui/skeleton"

/** Restores the session from the refresh cookie once, before any route renders. */
export function SessionGate({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const { status } = useSession()

  useEffect(() => {
    if (sessionStore.status() === "loading") void refreshSession()
  }, [])

  if (status === "loading") {
    // The shell's silhouette, so the first paint already has the app's shape.
    return (
      <div
        className="flex min-h-svh"
        role="status"
        aria-label={t("app.loading")}
      >
        <div className="hidden w-64 shrink-0 flex-col gap-3 border-r p-3 md:flex">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="mt-4 h-4 w-20" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
        <div className="flex flex-1 flex-col">
          <div className="flex h-14 items-center justify-end gap-2 border-b px-4">
            <Skeleton className="h-9 w-64" />
          </div>
          <div className="flex flex-col gap-4 px-10 py-10">
            <Skeleton className="h-8 w-72" />
            <Skeleton className="h-4 w-96" />
            <Skeleton className="mt-6 h-48 w-full max-w-2xl" />
          </div>
        </div>
      </div>
    )
  }
  return children
}

/** Signed-in screens. Anyone else goes to log in, and comes back after. */
export function RequireAuth() {
  const { status } = useSession()
  const location = useLocation()

  if (status !== "authenticated") {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return <Outlet />
}

/** Log in, sign up and recovery: pointless once signed in. */
export function GuestOnly() {
  const { status } = useSession()
  return status === "authenticated" ? <Navigate to="/" replace /> : <Outlet />
}
