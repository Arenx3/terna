import { useQuery } from "@tanstack/react-query"
import {
  ArrowLeftIcon,
  CircleAlertIcon,
  DownloadIcon,
  ExternalLinkIcon,
  UsersIcon,
} from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"

import {
  jobApplicationsQuery,
  resumeLink,
  type JobApplication,
} from "@/api/applications"
import { currentCompanyQuery } from "@/api/careers"
import { jobQuery } from "@/api/jobs"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { JobStatusBadge } from "@/components/jobs/job-status-badge"
import { JobTabs } from "@/components/jobs/job-tabs"
import { useStageLabel } from "@/components/jobs/stages-editor"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { initials, relativeTime } from "@/lib/format"

/**
 * Who applied to a job. The real-time board (#29) grows out of this list;
 * for now it answers "who is here, and where is their résumé".
 */
export function JobCandidatesPage() {
  const { t } = useTranslation()
  const { jobId = "" } = useParams()
  const { session } = useSession()
  const { canSeeJobs } = useRole()
  const companyId = session?.company.id ?? ""
  const job = useQuery({ ...jobQuery(companyId, jobId), enabled: canSeeJobs })
  const applications = useQuery({
    ...jobApplicationsQuery(companyId, jobId),
    enabled: canSeeJobs,
  })
  const company = useQuery({
    ...currentCompanyQuery(companyId),
    enabled: canSeeJobs,
  })
  useDocumentTitle(
    job.data
      ? `${t("candidates.tab")} · ${job.data.title}`
      : t("candidates.tab")
  )

  const back = (
    <Link
      to="/jobs"
      className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <ArrowLeftIcon aria-hidden="true" className="size-4" />
      {t("jobs.editor.back")}
    </Link>
  )

  if (job.isError) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <p className="text-sm text-muted-foreground">
          {t("jobs.editor.notFound")}
        </p>
      </div>
    )
  }

  const postingUrl =
    company.data && job.data?.status === "open"
      ? `/careers/${company.data.slug}/jobs/${jobId}`
      : null

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        {back}
        {job.data ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h1 className="min-w-0 text-[28px] leading-tight font-semibold tracking-[-0.03em] break-words">
              {job.data.title}
            </h1>
            <JobStatusBadge status={job.data.status} />
          </div>
        ) : (
          <Skeleton className="h-8 w-72" />
        )}
        <JobTabs jobId={jobId} />
      </header>

      {applications.isPending ? (
        <ListSkeleton />
      ) : applications.isError ? (
        <p role="alert" className="flex items-center gap-2 text-sm">
          <CircleAlertIcon
            aria-hidden="true"
            className="size-4 text-destructive"
          />
          {t("candidates.loadError")}
        </p>
      ) : applications.data.length === 0 ? (
        <Empty className="rounded-xl border border-dashed py-14">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <UsersIcon aria-hidden="true" />
            </EmptyMedia>
            <EmptyDescription>{t("candidates.empty")}</EmptyDescription>
          </EmptyHeader>
          {postingUrl ? (
            <EmptyContent>
              <a
                href={postingUrl}
                target="_blank"
                rel="noreferrer"
                className={buttonVariants({ variant: "outline" })}
              >
                <ExternalLinkIcon data-icon="inline-start" aria-hidden="true" />
                {t("candidates.sharePosting")}
              </a>
            </EmptyContent>
          ) : null}
        </Empty>
      ) : (
        <ul className="divide-y overflow-hidden rounded-xl border bg-card">
          {applications.data.map((application) => (
            <CandidateRow key={application.id} application={application} />
          ))}
        </ul>
      )}
    </div>
  )
}

function CandidateRow({ application }: { application: JobApplication }) {
  const { t, i18n } = useTranslation()
  const stageLabel = useStageLabel()
  const [opening, setOpening] = useState(false)
  const { candidate, resume } = application

  async function download() {
    setOpening(true)
    try {
      // An attachment: the browser downloads it and stays on this page.
      window.location.assign(await resumeLink(application.id))
    } finally {
      setOpening(false)
    }
  }

  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-5 py-3.5 md:grid-cols-[auto_minmax(0,1fr)_9rem_12rem_auto]">
      <span
        aria-hidden="true"
        className="grid size-8 place-items-center rounded-full border bg-muted text-xs font-medium"
      >
        {initials(candidate.full_name)}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-sm font-medium">
          {candidate.full_name}
        </span>
        <span className="truncate text-[13px] text-muted-foreground">
          {candidate.email}
        </span>
      </span>
      <span className="hidden text-[13px] text-muted-foreground md:block">
        {stageLabel(application.stage)}
      </span>
      <span className="hidden text-[13px] whitespace-nowrap text-faint-foreground md:block">
        {t("candidates.applied", {
          time: relativeTime(application.created_at, i18n.language),
        })}
      </span>
      {resume ? (
        <Button
          variant="outline"
          size="sm"
          disabled={opening}
          onClick={() => void download()}
          aria-label={t("candidates.downloadResume", {
            name: candidate.full_name,
          })}
        >
          <DownloadIcon data-icon="inline-start" aria-hidden="true" />
          {t("candidates.resume")}
        </Button>
      ) : (
        <span />
      )}
    </li>
  )
}

function ListSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="divide-y rounded-xl border"
    >
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-center gap-4 px-5 py-4">
          <Skeleton className="size-8 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3.5 w-48" />
            <Skeleton className="h-3 w-40" />
          </div>
          <Skeleton className="h-7 w-16" />
        </div>
      ))}
    </div>
  )
}
