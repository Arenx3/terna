import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeftIcon,
  CircleAlertIcon,
  ExternalLinkIcon,
  UsersIcon,
} from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"

import {
  jobApplicationsQuery,
  moveApplication,
  type JobApplication,
} from "@/api/applications"
import { currentCompanyQuery } from "@/api/careers"
import { ApiError, errorMessage } from "@/api/errors"
import { jobQuery } from "@/api/jobs"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import {
  JobBoard,
  type BoardStage,
  type MoveRequest,
} from "@/components/board/job-board"
import { JobStatusBadge } from "@/components/jobs/job-status-badge"
import { JobTabs } from "@/components/jobs/job-tabs"
import { useStageLabel } from "@/components/jobs/stages-editor"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { buttonVariants } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useBoardChannel,
  type BoardUpdate,
  type ChannelStatus,
  type Viewer,
} from "@/hooks/use-board-channel"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { initials } from "@/lib/format"
import { cn } from "@/lib/utils"

function upsert(list: JobApplication[] | undefined, next: JobApplication) {
  const current = list ?? []
  return current.some((item) => item.id === next.id)
    ? current.map((item) => (item.id === next.id ? next : item))
    : [next, ...current]
}

/** Who applied to a job, as a live board: everyone's moves show up as they happen. */
export function JobCandidatesPage() {
  const { t } = useTranslation()
  const { jobId = "" } = useParams()
  const { session } = useSession()
  const { canSeeJobs, canManageJobs } = useRole()
  const queryClient = useQueryClient()
  const label = useStageLabel()
  const companyId = session?.company.id ?? ""
  const listKey = jobApplicationsQuery(companyId, jobId).queryKey
  const [announcement, setAnnouncement] = useState("")
  const [failure, setFailure] = useState<string | null>(null)

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

  const { viewers, status } = useBoardChannel(jobId, {
    onReady: () => void queryClient.invalidateQueries({ queryKey: listKey }),
    onUpdate: (update: BoardUpdate) => {
      queryClient.setQueryData(listKey, (list: JobApplication[] | undefined) =>
        upsert(list, update.application)
      )
      if (update.by.id === session?.user.id) return // our own move, already announced
      const name = update.application.candidate.full_name
      setAnnouncement(
        update.event === "application.submitted"
          ? t("board.added", { name })
          : t("board.movedBy", {
              by: update.by.name,
              name,
              stage: label(update.application.stage),
            })
      )
    },
  })

  const move = useMutation({
    mutationFn: ({ application, stage, reason, note }: MoveRequest) =>
      moveApplication(application.id, {
        stage: stage.id,
        from_stage: application.stage.id,
        reason: reason ?? "",
        note: note ?? "",
      }),
    onMutate: async ({ application, stage, reason }: MoveRequest) => {
      setFailure(null)
      await queryClient.cancelQueries({ queryKey: listKey })
      const previous = queryClient.getQueryData<JobApplication[]>(listKey)
      queryClient.setQueryData(listKey, (list: JobApplication[] | undefined) =>
        upsert(list, {
          ...application,
          stage: { id: stage.id, name: stage.name, kind: stage.kind },
          stage_entered_at: new Date().toISOString(),
          rejection_reason: reason ?? "",
        })
      )
      setAnnouncement(
        t("board.moved", {
          name: application.candidate.full_name,
          stage: label(stage),
        })
      )
      return { previous }
    },
    onError: (error, { application }, context) => {
      queryClient.setQueryData(listKey, context?.previous)
      setFailure(
        error instanceof ApiError && error.code === "stage_changed"
          ? errorMessage(t, error)
          : t("board.moveFailed", { name: application.candidate.full_name })
      )
      void queryClient.invalidateQueries({ queryKey: listKey })
    },
    onSuccess: (saved) =>
      queryClient.setQueryData(listKey, (list: JobApplication[] | undefined) =>
        upsert(list, saved)
      ),
  })

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

  const stages = (job.data?.stages ?? []).filter(
    (stage): stage is BoardStage => typeof stage.id === "number"
  )
  const others = viewers.filter((viewer) => viewer.user.id !== session?.user.id)
  const postingUrl =
    company.data && job.data?.status === "open"
      ? `/careers/${company.data.slug}/jobs/${jobId}`
      : null

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4">
        {back}
        <div className="flex flex-wrap items-center justify-between gap-4">
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
          <Presence status={status} others={others} />
        </div>
        <JobTabs jobId={jobId} />
      </header>

      <span role="status" aria-live="polite" className="sr-only">
        {announcement}
      </span>
      {failure ? (
        <Alert variant="destructive">
          <CircleAlertIcon aria-hidden="true" />
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      ) : null}

      {applications.isPending || job.isPending ? (
        <BoardSkeleton />
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
        <JobBoard
          stages={stages}
          applications={applications.data}
          canMove={canManageJobs}
          onMove={(request) => move.mutate(request)}
        />
      )}
    </div>
  )
}

/** Whether the board is live, and who else is looking at it right now. */
function Presence({
  status,
  others,
}: {
  status: ChannelStatus
  others: Viewer[]
}) {
  const { t } = useTranslation()
  const shown = others.slice(0, 4)
  return (
    <div className="flex items-center gap-3">
      {others.length > 0 ? (
        <ul aria-label={t("board.alsoHere")} className="flex -space-x-1.5">
          {shown.map((viewer) => (
            <li
              key={viewer.key}
              title={viewer.user.name}
              className="grid size-7 place-items-center rounded-full border-2 border-background bg-muted text-[10px] font-medium"
            >
              <span aria-hidden="true">{initials(viewer.user.name)}</span>
              <span className="sr-only">{viewer.user.name}</span>
            </li>
          ))}
          {others.length > shown.length ? (
            <li className="grid size-7 place-items-center rounded-full border-2 border-background bg-muted text-[10px] text-muted-foreground">
              {t("board.more", { count: others.length - shown.length })}
            </li>
          ) : null}
        </ul>
      ) : null}
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span
          aria-hidden="true"
          className={cn(
            "size-2 rounded-full",
            status === "live" ? "bg-success" : "bg-faint-foreground/60"
          )}
        />
        {status === "live"
          ? t("board.live")
          : status === "connecting"
            ? t("board.connecting")
            : t("board.offline")}
      </span>
    </div>
  )
}

function BoardSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex gap-3 overflow-hidden"
    >
      {[0, 1, 2, 3].map((column) => (
        <div
          key={column}
          className="flex w-64 shrink-0 flex-col gap-2 rounded-xl border p-2"
        >
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ))}
    </div>
  )
}
