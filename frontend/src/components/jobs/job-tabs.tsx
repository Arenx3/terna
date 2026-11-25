import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { NavLink } from "react-router"

import { jobApplicationsQuery } from "@/api/applications"
import { useSession } from "@/auth/session"
import { cn } from "@/lib/utils"

/** A job's two faces: who applied, and how the job is set up. */
export function JobTabs({ jobId }: { jobId: string }) {
  const { t } = useTranslation()
  const { session } = useSession()
  const applications = useQuery(
    jobApplicationsQuery(session?.company.id ?? "", jobId)
  )
  const tab = ({ isActive }: { isActive: boolean }) =>
    cn(
      "-mb-px inline-flex items-center gap-2 border-b-2 px-1 pb-2.5 text-sm font-medium transition-colors focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
      isActive
        ? "border-foreground text-foreground"
        : "border-transparent text-muted-foreground hover:text-foreground"
    )

  return (
    <nav aria-label={t("candidates.tabsLabel")} className="flex gap-6 border-b">
      <NavLink to={`/jobs/${jobId}/candidates`} className={tab}>
        {t("candidates.tab")}
        {applications.data ? (
          <span className="font-mono text-xs text-faint-foreground tabular-nums">
            {applications.data.length}
          </span>
        ) : null}
      </NavLink>
      <NavLink to={`/jobs/${jobId}`} end className={tab}>
        {t("candidates.settingsTab")}
      </NavLink>
    </nav>
  )
}
