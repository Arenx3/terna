import { useQuery } from "@tanstack/react-query"
import {
  BriefcaseBusinessIcon,
  CircleAlertIcon,
  ExternalLinkIcon,
  LockIcon,
  PlusIcon,
} from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link, useSearchParams } from "react-router"

import { currentCompanyQuery } from "@/api/careers"
import { jobsQuery, type JobStatus, type JobSummary } from "@/api/jobs"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { JobStatusBadge } from "@/components/jobs/job-status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { initials } from "@/lib/format"

type Filter = JobStatus | "all"
const FILTERS: Filter[] = ["open", "draft", "closed", "all"]

function isFilter(value: string | null): value is Filter {
  return FILTERS.some((filter) => filter === value)
}

export function JobsPage() {
  const { t } = useTranslation()
  const { session } = useSession()
  const { canSeeJobs, canManageJobs } = useRole()
  const [params, setParams] = useSearchParams()
  useDocumentTitle(t("jobs.title"))

  const companyId = session?.company.id ?? ""
  const jobs = useQuery({ ...jobsQuery(companyId), enabled: canSeeJobs })
  const company = useQuery({
    ...currentCompanyQuery(companyId),
    enabled: canSeeJobs,
  })

  if (!canSeeJobs) {
    return (
      <Empty className="mt-10">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <LockIcon aria-hidden="true" />
          </EmptyMedia>
          <EmptyTitle>
            <h2>{t("jobs.forbidden.title")}</h2>
          </EmptyTitle>
          <EmptyDescription>{t("jobs.forbidden.description")}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  const raw = params.get("status")
  const filter: Filter = isFilter(raw) ? raw : "open"
  const all = jobs.data ?? []
  const count = (status: Filter) =>
    status === "all"
      ? all.length
      : all.filter((job) => job.status === status).length
  const visible =
    filter === "all" ? all : all.filter((job) => job.status === filter)

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-2">
          <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.03em]">
            {t("jobs.title")}
          </h1>
          <p className="text-pretty text-muted-foreground">
            {canManageJobs ? t("jobs.description") : t("jobs.descriptionOwner")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {company.data ? (
            <a
              href={`/careers/${company.data.slug}`}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ variant: "outline" })}
            >
              <ExternalLinkIcon data-icon="inline-start" aria-hidden="true" />
              {t("jobs.careersPage")}
            </a>
          ) : null}
          {canManageJobs ? (
            <Link to="/jobs/new" className={buttonVariants()}>
              <PlusIcon data-icon="inline-start" aria-hidden="true" />
              {t("jobs.new")}
            </Link>
          ) : null}
        </div>
      </div>

      {jobs.isPending ? (
        <JobListSkeleton />
      ) : jobs.isError ? (
        <div
          role="alert"
          className="flex items-center gap-3 rounded-xl border px-5 py-4 text-sm"
        >
          <CircleAlertIcon
            aria-hidden="true"
            className="size-4 text-destructive"
          />
          <span className="flex-1">{t("jobs.loadError")}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void jobs.refetch()}
          >
            {t("jobs.retry")}
          </Button>
        </div>
      ) : all.length === 0 ? (
        <Empty className="rounded-xl border border-dashed py-16">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BriefcaseBusinessIcon aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>
              <h2>
                {canManageJobs
                  ? t("jobs.empty.title")
                  : t("jobs.empty.ownerTitle")}
              </h2>
            </EmptyTitle>
            <EmptyDescription>
              {canManageJobs
                ? t("jobs.empty.description")
                : t("jobs.empty.ownerDescription")}
            </EmptyDescription>
          </EmptyHeader>
          {canManageJobs ? (
            <EmptyContent>
              <Link to="/jobs/new" className={buttonVariants()}>
                <PlusIcon data-icon="inline-start" aria-hidden="true" />
                {t("jobs.new")}
              </Link>
            </EmptyContent>
          ) : null}
        </Empty>
      ) : (
        <div className="flex flex-col gap-4">
          <Tabs
            value={filter}
            onValueChange={(next) =>
              setParams(next === "open" ? {} : { status: String(next) }, {
                replace: true,
              })
            }
          >
            <TabsList
              variant="line"
              aria-label={t("jobs.filter")}
              className="max-w-full justify-start overflow-x-auto"
            >
              {FILTERS.map((status) => (
                <TabsTrigger key={status} value={status} className="px-2.5">
                  {t(`jobs.tabs.${status}`)}
                  <span className="font-mono text-xs text-faint-foreground tabular-nums">
                    {count(status)}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {visible.length === 0 ? (
            <p className="rounded-xl border border-dashed px-5 py-10 text-center text-sm text-muted-foreground">
              {filter === "all"
                ? t("jobs.empty.title")
                : t(`jobs.empty.${filter}`)}
            </p>
          ) : (
            <ul className="divide-y overflow-hidden rounded-xl border bg-card">
              {visible.map((job) => (
                <JobRow key={job.id} job={job} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

function JobRow({ job }: { job: JobSummary }) {
  const { t } = useTranslation()
  const meta = [
    job.department,
    job.location,
    job.workplace ? t(`jobs.workplace.${job.workplace}`) : "",
  ].filter(Boolean)

  return (
    <li>
      <Link
        to={`/jobs/${job.id}`}
        className="group grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-2 px-5 py-4 transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset md:grid-cols-[minmax(0,1fr)_11rem_9rem_6rem]"
      >
        <div className="flex min-w-0 flex-col gap-1">
          <span className="line-clamp-2 text-[15px] font-medium break-words">
            {job.title}
          </span>
          <span className="truncate text-[13px] text-muted-foreground">
            {meta.join(" · ")}
          </span>
        </div>
        <JobStatusBadge
          status={job.status}
          className="justify-self-end md:order-last"
        />
        <span className="col-span-2 text-[13px] text-muted-foreground tabular-nums md:col-span-1">
          {t("jobs.mustCount", { count: job.must_haves })}
          <span className="text-faint-foreground">
            {" · "}
            {t("jobs.niceCount", { count: job.nice_to_haves })}
          </span>
        </span>
        <span className="hidden min-w-0 items-center gap-2 text-[13px] text-muted-foreground md:flex">
          {job.hiring_manager ? (
            <>
              <span
                aria-hidden="true"
                className="grid size-6 shrink-0 place-items-center rounded-full border bg-muted text-[10px] font-medium text-foreground"
              >
                {initials(job.hiring_manager.full_name)}
              </span>
              <span className="truncate">{job.hiring_manager.full_name}</span>
            </>
          ) : (
            <span className="text-faint-foreground">{t("jobs.noOwner")}</span>
          )}
        </span>
      </Link>
    </li>
  )
}

function JobListSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex flex-col gap-4"
    >
      <Skeleton className="h-8 w-80" />
      <div className="divide-y rounded-xl border">
        {[0, 1, 2, 3].map((row) => (
          <div key={row} className="flex items-center gap-6 px-5 py-4">
            <div className="flex flex-1 flex-col gap-2">
              <Skeleton className="h-4 w-56" />
              <Skeleton className="h-3 w-40" />
            </div>
            <Skeleton className="hidden h-3 w-32 md:block" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
    </div>
  )
}
