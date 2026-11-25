import { useTranslation } from "react-i18next"

import type { JobStatus } from "@/api/jobs"
import { cn } from "@/lib/utils"

const DOT: Record<JobStatus, string> = {
  open: "bg-success",
  draft: "border border-dashed border-faint-foreground",
  closed: "bg-faint-foreground/60",
}

/**
 * Status as a dot and a word, never colour alone. The marker colour stays
 * reserved for evidence and location, so "open" is the success green.
 */
export function JobStatusBadge({
  status,
  className,
}: {
  status: JobStatus
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap",
        status === "open" ? "text-foreground" : "text-muted-foreground",
        className
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-2 rounded-full", DOT[status])}
      />
      {t(`jobs.status.${status}`)}
    </span>
  )
}
