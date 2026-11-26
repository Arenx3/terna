import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowRightIcon,
  CircleAlertIcon,
  DownloadIcon,
  InboxIcon,
  MailIcon,
  UserPlusIcon,
  UsersIcon,
} from "lucide-react"
import { useEffect, useId, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import type { RejectionReason } from "@/api/applications"
import { ApiError } from "@/api/errors"
import type { StageKind } from "@/api/jobs"
import {
  commentsQuery,
  postComment,
  profileQuery,
  resumeUrl,
  setInterviewers,
  timelineQuery,
  type CandidateComment,
  type Profile,
  type Teammate,
  type TimelineEvent,
} from "@/api/profile"
import { membersQuery } from "@/api/team"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { JobStatusBadge } from "@/components/jobs/job-status-badge"
import { CandidateEmails } from "@/components/profile/candidate-emails"
import { useStageLabel } from "@/components/jobs/stages-editor"
import {
  mentionedIn,
  MentionTextarea,
} from "@/components/profile/mention-textarea"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { initials, relativeTime, shortDate } from "@/lib/format"

type Stage = { name: string; kind: StageKind }

/**
 * Everything about one candidate, for the people working on them: who they
 * are, where they stand, what happened, their résumé and the team's notes.
 * Used as a panel over the board and as a page of its own.
 */
export function CandidateProfile({
  applicationId,
  headingId,
  Heading = "h2",
}: {
  applicationId: number
  headingId?: string
  Heading?: "h1" | "h2"
}) {
  const { t } = useTranslation()
  const { session } = useSession()
  const companyId = session?.company.id ?? ""
  const profile = useQuery(profileQuery(companyId, applicationId))

  if (profile.isPending) return <ProfileSkeleton />
  if (profile.isError) {
    const missing =
      profile.error instanceof ApiError && profile.error.status === 404
    return (
      <p
        role="alert"
        className="flex items-center gap-2 text-sm text-muted-foreground"
      >
        <CircleAlertIcon aria-hidden="true" className="size-4" />
        {missing ? t("profile.notFound") : t("profile.loadError")}
      </p>
    )
  }
  return (
    <ProfileBody
      profile={profile.data}
      headingId={headingId}
      Heading={Heading}
    />
  )
}

function ProfileBody({
  profile,
  headingId,
  Heading,
}: {
  profile: Profile
  headingId?: string
  Heading: "h1" | "h2"
}) {
  const { t, i18n } = useTranslation()
  const stageLabel = useStageLabel()
  const { candidate } = profile

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className="grid size-11 shrink-0 place-items-center rounded-full border bg-muted text-sm font-medium"
          >
            {initials(candidate.full_name)}
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <Heading
              id={headingId}
              className="text-2xl leading-tight font-semibold tracking-[-0.025em] break-words"
            >
              {candidate.full_name}
            </Heading>
            <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <a
                href={`mailto:${candidate.email}`}
                className="underline-offset-4 hover:text-foreground hover:underline"
                translate="no"
              >
                {candidate.email}
              </a>
              {candidate.phone ? (
                <a
                  href={`tel:${candidate.phone}`}
                  className="underline-offset-4 hover:text-foreground hover:underline"
                >
                  {candidate.phone}
                </a>
              ) : null}
            </p>
          </div>
        </div>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="text-muted-foreground">{profile.job.title}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{stageLabel(profile.stage)}</span>
            {profile.rejection_reason ? (
              <span className="rounded-md border px-1.5 py-0.5 text-xs text-muted-foreground">
                {t(
                  `board.reasons.${profile.rejection_reason as RejectionReason}`
                )}
              </span>
            ) : null}
            <span className="text-faint-foreground">
              {t("profile.appliedOn", {
                date: shortDate(profile.created_at, i18n.language),
              })}
            </span>
          </dd>
          <dt className="text-muted-foreground">{t("profile.interviewers")}</dt>
          <dd>
            <Interviewers profile={profile} />
          </dd>
        </dl>
      </header>

      <Tabs defaultValue="activity" className="gap-5">
        <TabsList variant="line" className="w-full justify-start border-b">
          <TabsTrigger value="activity">
            {t("profile.tabs.activity")}
          </TabsTrigger>
          <TabsTrigger value="resume">{t("profile.tabs.resume")}</TabsTrigger>
          <TabsTrigger value="emails">{t("profile.tabs.emails")}</TabsTrigger>
          <TabsTrigger value="applications">
            {t("profile.tabs.applications")}
            <span className="font-mono text-xs text-faint-foreground tabular-nums">
              {profile.other_applications.length}
            </span>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="activity">
          <Activity profile={profile} />
        </TabsContent>
        <TabsContent value="resume">
          <ResumeViewer profile={profile} />
        </TabsContent>
        <TabsContent value="emails">
          <CandidateEmails profile={profile} />
        </TabsContent>
        <TabsContent value="applications">
          <OtherApplications profile={profile} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Interviewers({ profile }: { profile: Profile }) {
  const { t } = useTranslation()
  const { session } = useSession()
  const { isAdmin, canManageJobs } = useRole()
  const queryClient = useQueryClient()
  const companyId = session?.company.id ?? ""
  const members = useQuery({
    ...membersQuery(companyId),
    enabled: canManageJobs,
  })
  const interviewerMembers = (members.data ?? []).filter(
    (member) => member.role === "interviewer"
  )
  const assigned = new Set(profile.interviewers.map((person) => person.id))

  const save = useMutation({
    mutationFn: (users: string[]) => setInterviewers(profile.id, users),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["applications", companyId, profile.id],
      }),
  })

  const names = profile.interviewers
    .map((person) => person.full_name)
    .join(", ")
  const summary = (
    <span className={names ? "" : "text-faint-foreground"}>
      {names || t("profile.noInterviewers")}
    </span>
  )
  if (!profile.can_manage || !(isAdmin || canManageJobs)) return summary

  return (
    <div className="flex flex-wrap items-center gap-2">
      {summary}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="xs" disabled={save.isPending}>
              <UserPlusIcon data-icon="inline-start" aria-hidden="true" />
              {t("profile.assign")}
            </Button>
          }
        />
        <DropdownMenuContent align="start" className="min-w-56">
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("profile.interviewers")}</DropdownMenuLabel>
            {interviewerMembers.length === 0 ? (
              <p className="px-2 py-1.5 text-sm text-muted-foreground">
                {t("profile.noInterviewerMembers")}
              </p>
            ) : (
              interviewerMembers.map((member) => (
                <DropdownMenuCheckboxItem
                  key={member.user.id}
                  checked={assigned.has(member.user.id)}
                  closeOnClick={false}
                  onCheckedChange={(checked) => {
                    const next = new Set(assigned)
                    if (checked) next.add(member.user.id)
                    else next.delete(member.user.id)
                    save.mutate([...next])
                  }}
                >
                  {member.user.full_name}
                </DropdownMenuCheckboxItem>
              ))
            )}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {save.isError ? (
        <span role="alert" className="text-xs text-destructive">
          {t("profile.assignFailed")}
        </span>
      ) : null}
    </div>
  )
}

type Item =
  | { kind: "comment"; at: string; comment: CandidateComment }
  | { kind: "event"; at: string; event: TimelineEvent }

function Activity({ profile }: { profile: Profile }) {
  const { t } = useTranslation()
  const { session } = useSession()
  const companyId = session?.company.id ?? ""
  const queryClient = useQueryClient()
  const comments = useQuery(commentsQuery(companyId, profile.id))
  const timeline = useQuery(timelineQuery(companyId, profile.id))
  const composerId = useId()
  const [draft, setDraft] = useState("")

  const send = useMutation({
    mutationFn: () =>
      postComment(profile.id, draft.trim(), mentionedIn(draft, profile.team)),
    onSuccess: (comment) => {
      queryClient.setQueryData(
        commentsQuery(companyId, profile.id).queryKey,
        (list: CandidateComment[] | undefined) => [...(list ?? []), comment]
      )
      setDraft("")
    },
  })

  const items: Item[] = [
    ...(comments.data ?? []).map((comment): Item => ({
      kind: "comment",
      at: comment.created_at,
      comment,
    })),
    ...(timeline.data ?? []).map((event): Item => ({
      kind: "event",
      at: event.occurred_at,
      event,
    })),
  ].sort((a, b) => b.at.localeCompare(a.at))

  return (
    <div className="flex flex-col gap-5">
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (draft.trim()) send.mutate()
        }}
      >
        <MentionTextarea
          id={composerId}
          value={draft}
          onChange={setDraft}
          people={profile.team}
          label={t("profile.commentLabel")}
          describedBy={`${composerId}-hint`}
          placeholder={t("profile.commentPlaceholder")}
          disabled={send.isPending}
          onSubmit={() => draft.trim() && send.mutate()}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p
            id={`${composerId}-hint`}
            className="text-xs text-faint-foreground"
          >
            {t("profile.commentHint")}
          </p>
          <Button
            type="submit"
            size="sm"
            disabled={!draft.trim() || send.isPending}
          >
            {send.isPending ? t("profile.commenting") : t("profile.comment")}
          </Button>
        </div>
        {send.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {t("profile.commentFailed")}
          </p>
        ) : null}
      </form>

      {comments.isPending || timeline.isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("profile.noActivity")}
        </p>
      ) : (
        <ol className="flex flex-col gap-4">
          {items.map((item) =>
            item.kind === "comment" ? (
              <CommentItem
                key={`c-${item.comment.id}`}
                comment={item.comment}
                team={profile.team}
              />
            ) : (
              <EventItem
                key={`e-${item.event.id}`}
                event={item.event}
                profile={profile}
              />
            )
          )}
        </ol>
      )}
    </div>
  )
}

/** A comment, with its @mentions set apart so the eye finds them. */
function CommentItem({
  comment,
  team,
}: {
  comment: CandidateComment
  team: Teammate[]
}) {
  const { i18n } = useTranslation()
  const names = team
    .map((person) => `@${person.full_name}`)
    .sort((a, b) => b.length - a.length)
  const pattern = names.length
    ? new RegExp(
        `(${names.map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`
      )
    : null
  const parts = pattern ? comment.body.split(pattern) : [comment.body]

  return (
    <li className="flex gap-3">
      <span
        aria-hidden="true"
        className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full border bg-muted text-[10px] font-medium"
      >
        {initials(comment.author_name)}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1 rounded-lg border bg-card px-3.5 py-2.5">
        <p className="flex items-baseline justify-between gap-3 text-xs">
          <span className="font-medium">{comment.author_name}</span>
          <time dateTime={comment.created_at} className="text-faint-foreground">
            {relativeTime(comment.created_at, i18n.language)}
          </time>
        </p>
        <p className="text-sm leading-relaxed break-words whitespace-pre-line">
          {parts.map((part, index) =>
            names.includes(part) ? (
              <span key={index} className="font-medium text-foreground">
                {part}
              </span>
            ) : (
              <span key={index}>{part}</span>
            )
          )}
        </p>
      </div>
    </li>
  )
}

function EventItem({
  event,
  profile,
}: {
  event: TimelineEvent
  profile: Profile
}) {
  const { t, i18n } = useTranslation()
  const stageLabel = useStageLabel()
  const payload = (event.payload ?? {}) as {
    to?: Stage
    job_title?: string
    interviewers?: string[]
    subject?: string
  }
  const actor = event.actor_name || t("audit.system")
  const otherJob = event.entity_id !== String(profile.id)

  const [Icon, text] =
    event.type === "application.submitted"
      ? [InboxIcon, t("profile.events.submitted", { job: event.entity_label })]
      : event.type === "application.stage_changed"
        ? [
            ArrowRightIcon,
            otherJob
              ? t("profile.events.movedIn", {
                  actor,
                  stage: payload.to ? stageLabel(payload.to) : "",
                  job: payload.job_title,
                })
              : t("profile.events.moved", {
                  actor,
                  stage: payload.to ? stageLabel(payload.to) : "",
                }),
          ]
        : event.type === "email.sent"
          ? [
              MailIcon,
              t("profile.events.emailed", { actor, subject: payload.subject }),
            ]
          : [
              UsersIcon,
              t("profile.events.assigned", {
                actor,
                names: (payload.interviewers ?? []).join(", "),
              }),
            ]

  return (
    <li className="flex items-start gap-3 pl-1 text-sm text-muted-foreground">
      <span className="grid size-5 shrink-0 place-items-center">
        <Icon aria-hidden="true" className="size-3.5" />
      </span>
      <span className="flex-1">{text}</span>
      <time
        dateTime={event.occurred_at}
        className="shrink-0 text-xs text-faint-foreground"
      >
        {relativeTime(event.occurred_at, i18n.language)}
      </time>
    </li>
  )
}

/** The résumé, shown in the browser when it's a PDF. The file comes straight from storage. */
function ResumeViewer({ profile }: { profile: Profile }) {
  const { t } = useTranslation()
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const resume = profile.resume
  const isPdf = resume?.format === "pdf"

  useEffect(() => {
    if (!isPdf) return
    let objectUrl: string | null = null
    let cancelled = false
    // A blob URL is same-origin, so the browser's PDF viewer can frame it.
    resumeUrl(profile.id, true)
      .then((url) => fetch(url))
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(
          new Blob([blob], { type: "application/pdf" })
        )
        setSrc(objectUrl)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [profile.id, isPdf])

  async function download() {
    window.location.assign(await resumeUrl(profile.id, false))
  }

  if (!resume) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("profile.resume.none")}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <span className="truncate text-sm text-muted-foreground">
          {resume.filename}
        </span>
        <Button variant="outline" size="sm" onClick={() => void download()}>
          <DownloadIcon data-icon="inline-start" aria-hidden="true" />
          {t("profile.resume.download")}
        </Button>
      </div>
      {!isPdf ? (
        <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          {t("profile.resume.wordNoPreview")}
        </p>
      ) : failed ? (
        <p role="alert" className="text-sm text-destructive">
          {t("profile.resume.loadError")}
        </p>
      ) : src ? (
        <iframe
          src={src}
          title={t("profile.resume.title", {
            name: profile.candidate.full_name,
          })}
          className="h-[70vh] w-full rounded-lg border bg-white"
        />
      ) : (
        <Skeleton className="h-[70vh] w-full" />
      )}
    </div>
  )
}

function OtherApplications({ profile }: { profile: Profile }) {
  const { t, i18n } = useTranslation()
  const stageLabel = useStageLabel()
  if (profile.other_applications.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("profile.noOtherApplications")}
      </p>
    )
  }
  return (
    <section className="flex flex-col gap-2">
      <h3 className="font-sans text-sm font-medium">
        {t("profile.otherApplications")}
      </h3>
      <ul className="divide-y rounded-lg border">
        {profile.other_applications.map((other) => (
          <li
            key={other.id}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3"
          >
            <Link
              to={`/jobs/${other.job.id}/candidates/${other.id}`}
              className="min-w-0 flex-1 truncate text-sm font-medium underline-offset-4 hover:underline"
            >
              {other.job.title}
            </Link>
            <span className="text-[13px] text-muted-foreground">
              {stageLabel(other.stage)}
            </span>
            <JobStatusBadge status={other.job.status} />
            <span className="text-xs text-faint-foreground">
              {relativeTime(other.created_at, i18n.language)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function ProfileSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex flex-col gap-4"
    >
      <div className="flex items-center gap-3">
        <Skeleton className="size-11 rounded-full" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-3.5 w-56" />
        </div>
      </div>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
