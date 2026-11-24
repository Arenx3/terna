import { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, Outlet, useLocation } from "react-router"

import { refreshSession, sessionStore, useSession } from "@/auth/session"
import { Spinner } from "@/components/ui/spinner"

/** Restores the session from the refresh cookie once, before any route renders. */
export function SessionGate({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const { status } = useSession()

  useEffect(() => {
    if (sessionStore.status() === "loading") void refreshSession()
  }, [])

  if (status === "loading") {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner
          aria-label={t("app.loading")}
          className="size-5 text-muted-foreground"
        />
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
