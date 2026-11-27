import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CircleAlertIcon,
  FileTextIcon,
  RotateCwIcon,
  ScanEyeIcon,
} from "lucide-react"
import { useId, useState, type ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { errorMessage } from "@/api/errors"
import {
  isReading,
  reprocessResume,
  resumeTextQuery,
  type Passage,
  type RedactionKind,
  type ResumeText,
  type Section,
} from "@/api/screening"
import { useSession } from "@/auth/session"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Toggle } from "@/components/ui/toggle"

type Group = { section: Section; passages: Passage[] }

/** Consecutive passages of the same section, in reading order. */
function groupBySection(passages: Passage[]): Group[] {
  const groups: Group[] = []
  for (const passage of passages) {
    const last = groups.at(-1)
    if (last && last.section === passage.section) last.passages.push(passage)
    else groups.push({ section: passage.section, passages: [passage] })
  }
  return groups
}

/**
 * What the screening read from the résumé, section by section: the same lines
 * it cites as evidence. Dates it understood are set apart, so a recruiter can
 * check them at a glance.
 */
export function ResumeTextView({
  applicationId,
  canManage,
  onShowDocument,
}: {
  applicationId: number
  canManage: boolean
  /** Switch to the original file, when there is a preview to switch to. */
  onShowDocument?: () => void
}) {
  const { t } = useTranslation()
  const { session } = useSession()
  const companyId = session?.company.id ?? ""
  const queryClient = useQueryClient()
  const query = resumeTextQuery(companyId, applicationId)
  const text = useQuery(query)
  const reprocess = useMutation({
    mutationFn: () => reprocessResume(applicationId),
    onSuccess: (data) => queryClient.setQueryData(query.queryKey, data),
  })

  if (text.isPending) return <TextSkeleton />
  if (text.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t("profile.resume.text.loadError")}
      </p>
    )
  }

  const data = text.data
  const readAgain = canManage ? (
    <Button
      variant={data.status === "ready" ? "ghost" : "outline"}
      size="sm"
      disabled={reprocess.isPending}
      onClick={() => reprocess.mutate()}
    >
      <RotateCwIcon data-icon="inline-start" aria-hidden="true" />
      {data.status === "failed"
        ? t("profile.resume.text.retry")
        : t("profile.resume.text.readAgain")}
    </Button>
  ) : null
  const reprocessError = reprocess.isError ? (
    <p role="alert" className="text-sm text-destructive">
      {errorMessage(t, reprocess.error)}
    </p>
  ) : null

  if (isReading(data.status)) {
    return (
      <div className="flex flex-col gap-4">
        <p
          role="status"
          className="flex items-center gap-2 text-sm text-muted-foreground"
        >
          <Spinner aria-hidden="true" />
          {t("profile.resume.text.reading")}
        </p>
        <TextSkeleton />
      </div>
    )
  }

  if (data.status === "needs_review" || data.status === "failed") {
    const failed = data.status === "failed"
    return (
      <div className="flex flex-col gap-3">
        <Alert variant={failed ? "destructive" : "default"}>
          <CircleAlertIcon aria-hidden="true" />
          <AlertTitle>
            {failed
              ? t("profile.resume.text.failedTitle")
              : t("profile.resume.text.reviewTitle")}
          </AlertTitle>
          <AlertDescription>
            <p>
              {data.reason
                ? t(`profile.resume.text.reason.${data.reason}`)
                : t("profile.resume.text.reason.error")}{" "}
              {failed
                ? t("profile.resume.text.failedHint")
                : t("profile.resume.text.reviewHint")}
            </p>
            {failed && data.detail ? (
              <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
                {data.detail}
              </p>
            ) : null}
          </AlertDescription>
        </Alert>
        <div className="flex flex-wrap gap-2">
          {onShowDocument ? (
            <Button variant="outline" size="sm" onClick={onShowDocument}>
              <FileTextIcon data-icon="inline-start" aria-hidden="true" />
              {t("profile.resume.text.showDocument")}
            </Button>
          ) : null}
          {readAgain}
        </div>
        {reprocessError}
      </div>
    )
  }

  return (
    <ReadText data={data} action={readAgain} actionError={reprocessError} />
  )
}

function ReadText({
  data,
  action,
  actionError,
}: {
  data: ResumeText
  action: ReactNode
  actionError: ReactNode
}) {
  const { t } = useTranslation()
  const [aiView, setAiView] = useState(false)
  const groups = groupBySection(data.passages)
  const hidden = data.passages.reduce(
    (total, passage) => total + passage.redactions.length,
    0
  )
  const pages = t("profile.resume.text.pages", { count: data.pages })
  const passages = t("profile.resume.text.passages", {
    count: data.passages.length,
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">
            {t("profile.resume.text.summary", { pages, passages })}
          </p>
          <p className="text-xs text-pretty text-muted-foreground">
            {aiView
              ? t("profile.resume.text.aiExplainer", { count: hidden })
              : t("profile.resume.text.explainer")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Toggle
            variant="outline"
            size="sm"
            pressed={aiView}
            onPressedChange={setAiView}
            className="data-pressed:bg-secondary"
          >
            <ScanEyeIcon data-icon="inline-start" aria-hidden="true" />
            {t("profile.resume.text.aiView")}
          </Toggle>
          {action}
        </div>
      </div>
      {actionError}
      {groups.map((group) => (
        <SectionBlock
          key={group.passages[0].id}
          group={group}
          showPages={data.pages > 1}
          aiView={aiView}
        />
      ))}
    </div>
  )
}

function SectionBlock({
  group,
  showPages,
  aiView,
}: {
  group: Group
  showPages: boolean
  aiView: boolean
}) {
  const { t } = useTranslation()
  const headingId = useId()
  const first = group.passages[0].page
  const last = group.passages.at(-1)?.page ?? first
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <h4
        id={headingId}
        className="flex items-baseline gap-2 text-[11px] font-medium tracking-wider text-muted-foreground uppercase"
      >
        {t(`profile.resume.text.section.${group.section}`)}
        {showPages ? (
          <span className="font-mono tracking-normal normal-case tabular-nums">
            {first === last
              ? t("profile.resume.text.page", { page: first })
              : t("profile.resume.text.pageRange", { from: first, to: last })}
          </span>
        ) : null}
      </h4>
      <ul className="flex flex-col gap-1.5 border-l pl-3">
        {group.passages.map((passage) => (
          <li key={passage.id} className="text-sm/relaxed text-pretty">
            <PassageText passage={passage} aiView={aiView} />
          </li>
        ))}
      </ul>
    </section>
  )
}

type Mark =
  | { start: number; end: number; type: "period" }
  | { start: number; end: number; type: "hidden"; kind: RedactionKind }

/** Where each date range sits in the passage, found in reading order. */
function periodMarks(passage: Passage): Mark[] {
  const marks: Mark[] = []
  let from = 0
  for (const period of passage.periods) {
    const start = passage.text.indexOf(period.text, from)
    if (start < 0) continue
    marks.push({ start, end: start + period.text.length, type: "period" })
    from = start + period.text.length
  }
  return marks
}

/**
 * The passage, with each date range it understood set in a mono chip. In the AI's
 * view, personal data is replaced by a marker of what it was, as the AI reads it.
 */
function PassageText({
  passage,
  aiView,
}: {
  passage: Passage
  aiView: boolean
}) {
  const { t } = useTranslation()
  const hidden: Mark[] = aiView
    ? passage.redactions.map((r) => ({ ...r, type: "hidden" }))
    : []
  // A date inside hidden data (a birth date) stays hidden.
  const marks = [
    ...hidden,
    ...periodMarks(passage).filter(
      (p) => !hidden.some((h) => p.start < h.end && h.start < p.end)
    ),
  ].sort((a, b) => a.start - b.start)

  const parts: ReactNode[] = []
  let cursor = 0
  for (const mark of marks) {
    if (mark.start > cursor) parts.push(passage.text.slice(cursor, mark.start))
    parts.push(
      mark.type === "hidden" ? (
        <span
          key={mark.start}
          className="rounded-sm border border-dashed border-muted-foreground/40 px-1 text-[0.6875rem] font-medium tracking-wide whitespace-nowrap text-muted-foreground uppercase"
        >
          {t(`profile.resume.text.hidden.${mark.kind}`)}
        </span>
      ) : (
        <span
          key={mark.start}
          className="rounded-sm bg-muted px-0.5 font-mono text-[0.8125rem] whitespace-nowrap text-foreground tabular-nums"
        >
          {passage.text.slice(mark.start, mark.end)}
        </span>
      )
    )
    cursor = mark.end
  }
  parts.push(passage.text.slice(cursor))
  return <>{parts}</>
}

function TextSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-hidden="true">
      {[3, 4, 2].map((lines, group) => (
        <div key={group} className="flex flex-col gap-2">
          <Skeleton className="h-3 w-24" />
          <div className="flex flex-col gap-2 border-l pl-3">
            {Array.from({ length: lines }, (_, line) => (
              <Skeleton
                key={line}
                className={line % 2 ? "h-4 w-4/5" : "h-4 w-full"}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
