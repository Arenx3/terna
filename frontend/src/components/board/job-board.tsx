import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { CheckIcon, DownloadIcon, EllipsisVerticalIcon } from "lucide-react"
import { useId, useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import {
  REJECTION_REASONS,
  resumeLink,
  type JobApplication,
  type RejectionReason,
} from "@/api/applications"
import type { Stage } from "@/api/jobs"
import { emailDraft } from "@/api/messaging"
import { ChoiceSelect } from "@/components/choice-select"
import { useStageLabel } from "@/components/jobs/stages-editor"
import { scheduledFor, type When } from "@/components/profile/candidate-emails"
import { VerdictMeter } from "@/components/screening/verdict-meter"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { initials, relativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

export type BoardStage = Stage & { id: number }
export type RejectionEmail = {
  subject: string
  body: string
  scheduled_for: string | null
}
export type MoveRequest = {
  application: JobApplication
  stage: BoardStage
  reason?: RejectionReason
  note?: string
  /** The rejection email to queue once the move is saved. */
  email?: RejectionEmail | null
}

/**
 * The pipeline as columns. Cards move by dragging (pointer) or from their
 * menu (keyboard and screen readers): select, choose the stage, confirm.
 * Rejecting always asks why.
 */
export function JobBoard({
  stages,
  applications,
  canMove,
  onMove,
  profileHref,
}: {
  stages: BoardStage[]
  applications: JobApplication[]
  canMove: boolean
  onMove: (request: MoveRequest) => void
  /** Where a card's name leads: the candidate's profile. */
  profileHref: (application: JobApplication) => string
}) {
  const { t } = useTranslation()
  const instructionsId = useId()
  const [dragging, setDragging] = useState<JobApplication | null>(null)
  const [rejecting, setRejecting] = useState<MoveRequest | null>(null)
  // Keyboard users move cards from their menu; dragging is for pointers.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  )

  function request(application: JobApplication, stage: BoardStage) {
    if (stage.id === application.stage.id) return
    if (stage.kind === "rejected") setRejecting({ application, stage })
    else onMove({ application, stage })
  }

  function onDragStart({ active }: DragStartEvent) {
    setDragging(active.data.current?.application ?? null)
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    setDragging(null)
    const application = active.data.current?.application as
      JobApplication | undefined
    const stage = stages.find((item) => `stage-${item.id}` === over?.id)
    if (application && stage) request(application, stage)
  }

  return (
    <section aria-label={t("board.label")} aria-describedby={instructionsId}>
      <p id={instructionsId} className="sr-only">
        {t("board.instructions")}
      </p>
      <DndContext
        sensors={sensors}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={() => setDragging(null)}
      >
        <div className="-mx-6 flex gap-3 overflow-x-auto px-6 pb-4 lg:-mx-10 lg:px-10">
          {stages.map((stage) => (
            <Column
              key={stage.id}
              stage={stage}
              applications={applications.filter(
                (item) => item.stage.id === stage.id
              )}
              stages={stages}
              canMove={canMove}
              onRequest={request}
              profileHref={profileHref}
            />
          ))}
        </div>
        <DragOverlay dropAnimation={null}>
          {dragging ? (
            <CardBody
              application={dragging}
              className="rotate-1 bg-popover ring-1 ring-border"
            />
          ) : null}
        </DragOverlay>
      </DndContext>

      <RejectDialog
        request={rejecting}
        onCancel={() => setRejecting(null)}
        onConfirm={(reason, note, email) => {
          if (rejecting) onMove({ ...rejecting, reason, note, email })
          setRejecting(null)
        }}
      />
    </section>
  )
}

function Column({
  stage,
  stages,
  applications,
  canMove,
  onRequest,
  profileHref,
}: {
  stage: BoardStage
  stages: BoardStage[]
  applications: JobApplication[]
  canMove: boolean
  onRequest: (application: JobApplication, stage: BoardStage) => void
  profileHref: (application: JobApplication) => string
}) {
  const { t } = useTranslation()
  const label = useStageLabel()
  const headingId = useId()
  const { setNodeRef, isOver } = useDroppable({ id: `stage-${stage.id}` })

  return (
    <section
      ref={setNodeRef}
      aria-labelledby={headingId}
      className={cn(
        "flex w-64 shrink-0 flex-col gap-2 rounded-xl border bg-muted/40 p-2 transition-colors",
        isOver && "border-primary-edge bg-muted"
      )}
    >
      <h2
        id={headingId}
        className="flex items-baseline justify-between gap-2 px-2 pt-1 font-sans text-[13px] font-medium"
      >
        <span className="truncate">{label(stage)}</span>{" "}
        <span className="font-mono text-xs text-faint-foreground tabular-nums">
          {applications.length}
        </span>
      </h2>
      <ol className="flex min-h-24 flex-col gap-2">
        {applications.length === 0 ? (
          <li className="grid h-20 place-items-center rounded-lg border border-dashed text-xs text-faint-foreground">
            {t("board.emptyColumn")}
          </li>
        ) : (
          applications.map((application) => (
            <Card
              key={application.id}
              application={application}
              stages={stages}
              canMove={canMove}
              onRequest={onRequest}
              href={profileHref(application)}
            />
          ))
        )}
      </ol>
    </section>
  )
}

function Card({
  application,
  stages,
  canMove,
  onRequest,
  href,
}: {
  application: JobApplication
  stages: BoardStage[]
  canMove: boolean
  onRequest: (application: JobApplication, stage: BoardStage) => void
  href: string
}) {
  const { t } = useTranslation()
  const label = useStageLabel()
  const { setNodeRef, listeners, isDragging } = useDraggable({
    id: `application-${application.id}`,
    data: { application },
    disabled: !canMove,
  })
  const name = application.candidate.full_name

  async function download() {
    window.location.assign(await resumeLink(application.id))
  }

  return (
    <li
      ref={setNodeRef}
      {...listeners}
      className={cn(
        "touch-none",
        canMove && "cursor-grab",
        isDragging && "opacity-40"
      )}
    >
      <CardBody
        application={application}
        href={href}
        menu={
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t("board.actionsFor", { name })}
                  className="text-faint-foreground hover:text-foreground"
                />
              }
            >
              <EllipsisVerticalIcon aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-48">
              {canMove ? (
                <>
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>{t("board.moveTo")}</DropdownMenuLabel>
                    {stages.map((stage) => {
                      const current = stage.id === application.stage.id
                      return (
                        <DropdownMenuItem
                          key={stage.id}
                          disabled={current}
                          onClick={() => onRequest(application, stage)}
                        >
                          <CheckIcon
                            aria-hidden="true"
                            className={cn(!current && "invisible")}
                          />
                          {label(stage)}
                        </DropdownMenuItem>
                      )
                    })}
                  </DropdownMenuGroup>
                  {application.resume ? <DropdownMenuSeparator /> : null}
                </>
              ) : null}
              {application.resume ? (
                <DropdownMenuItem onClick={() => void download()}>
                  <DownloadIcon aria-hidden="true" />
                  {t("candidates.downloadResume", { name })}
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        }
      />
    </li>
  )
}

function CardBody({
  application,
  href,
  menu,
  className,
}: {
  application: JobApplication
  href?: string
  menu?: ReactNode
  className?: string
}) {
  const { t, i18n } = useTranslation()
  const { candidate } = application
  return (
    <div
      className={cn(
        "relative flex flex-col gap-2 rounded-lg border bg-card p-3 transition-colors has-[a:hover]:border-foreground/20",
        className
      )}
    >
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className="mt-px grid size-6 shrink-0 place-items-center rounded-full border bg-muted text-[10px] font-medium"
        >
          {initials(candidate.full_name)}
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          {href ? (
            // The whole card is the link's target area; the name carries the label.
            <Link
              to={href}
              className="truncate rounded-sm text-sm font-medium after:absolute after:inset-0 after:rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {candidate.full_name}
            </Link>
          ) : (
            <span className="truncate text-sm font-medium">
              {candidate.full_name}
            </span>
          )}
          <span className="truncate text-xs text-muted-foreground">
            {candidate.email}
          </span>
        </span>
        {menu ? <span className="relative z-10">{menu}</span> : null}
      </div>
      <CardScreening screening={application.screening} />
      <div className="flex items-center justify-between gap-2 text-xs text-faint-foreground">
        <span>
          {t("board.inStage", {
            time: relativeTime(application.stage_entered_at, i18n.language),
          })}
        </span>
        {application.rejection_reason ? (
          <span className="truncate rounded-md border px-1.5 py-0.5 text-muted-foreground">
            {t(
              `board.reasons.${application.rejection_reason as RejectionReason}`
            )}
          </span>
        ) : null}
      </div>
    </div>
  )
}

/** How the résumé measures up, at a glance; the profile has the evidence. */
function CardScreening({
  screening,
}: {
  screening: JobApplication["screening"]
}) {
  const { t } = useTranslation()
  if (!screening || screening.status === "waiting") return null
  if (screening.status === "pending" || screening.status === "processing") {
    return (
      <span className="flex items-center gap-2 text-xs text-faint-foreground">
        <span
          aria-hidden="true"
          className="h-1.5 flex-1 animate-pulse rounded-[2px] bg-foreground/10"
        />
        {t("board.screening.running")}
      </span>
    )
  }
  if (screening.status === "failed") {
    return (
      <span className="text-xs text-faint-foreground">
        {t("board.screening.failed")}
      </span>
    )
  }
  if (screening.must_total + screening.nice_total === 0) return null
  return (
    <span className="flex items-center gap-2">
      <VerdictMeter counts={screening} className="flex-1" />
      <span
        aria-hidden="true"
        className="font-mono text-[11px] whitespace-nowrap text-muted-foreground tabular-nums"
      >
        {t("board.screening.must", {
          meets: screening.must_meets,
          total: screening.must_total,
        })}
      </span>
    </span>
  )
}

function RejectDialog({
  request,
  onCancel,
  onConfirm,
}: {
  request: MoveRequest | null
  onCancel: () => void
  onConfirm: (
    reason: RejectionReason,
    note: string,
    email: RejectionEmail | null
  ) => void
}) {
  return (
    <AlertDialog
      open={request !== null}
      onOpenChange={(open) => {
        if (!open) onCancel()
      }}
    >
      <AlertDialogContent className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-lg">
        {request ? (
          <RejectForm
            key={request.application.id}
            request={request}
            onConfirm={onConfirm}
          />
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  )
}

function RejectForm({
  request,
  onConfirm,
}: {
  request: MoveRequest
  onConfirm: (
    reason: RejectionReason,
    note: string,
    email: RejectionEmail | null
  ) => void
}) {
  const { t } = useTranslation()
  const [reason, setReason] = useState<RejectionReason>("requirements")
  const [note, setNote] = useState("")
  const [withEmail, setWithEmail] = useState(true)
  // Read late at night a rejection lands harder: by default it goes out tomorrow morning.
  const [when, setWhen] = useState<When>("tomorrow")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const ids = {
    note: useId(),
    email: useId(),
    when: useId(),
    subject: useId(),
    body: useId(),
  }
  const name = request.application.candidate.full_name

  const draft = useQuery({
    queryKey: ["email-draft", request.application.id, "rejection"],
    queryFn: () => emailDraft(request.application.id, "rejection"),
    staleTime: 0,
    gcTime: 0,
  })
  // Start from the template once it arrives (adjusting state while rendering).
  const [loaded, setLoaded] = useState(false)
  if (draft.data && !loaded) {
    setLoaded(true)
    setSubject(draft.data.subject)
    setBody(draft.data.body)
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const email =
          withEmail && subject.trim() && body.trim()
            ? {
                subject: subject.trim(),
                body: body.trim(),
                scheduled_for: scheduledFor(when),
              }
            : null
        onConfirm(reason, note.trim(), email)
      }}
      className="flex flex-col gap-4"
    >
      <AlertDialogHeader>
        <AlertDialogTitle>{t("board.reject.title", { name })}</AlertDialogTitle>
        <AlertDialogDescription>
          {t("board.reject.description")}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">
          {t("board.reject.reason")}
        </legend>
        {REJECTION_REASONS.map((value) => (
          <label key={value} className="flex items-center gap-2.5 text-sm">
            <input
              type="radio"
              name="reason"
              value={value}
              checked={reason === value}
              onChange={() => setReason(value)}
              className="size-4 accent-[var(--primary-edge)]"
            />
            {t(`board.reasons.${value}`)}
          </label>
        ))}
      </fieldset>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={ids.note} className="text-sm font-medium">
          {t("board.reject.note")}{" "}
          <span className="font-normal text-faint-foreground">
            {t("board.reject.optional")}
          </span>
        </label>
        <Textarea
          id={ids.note}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          maxLength={1000}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-lg border p-3">
        <label htmlFor={ids.email} className="flex items-start gap-2.5 text-sm">
          <input
            id={ids.email}
            type="checkbox"
            checked={withEmail}
            onChange={(event) => setWithEmail(event.target.checked)}
            className="mt-0.5 size-4 accent-[var(--primary-edge)]"
          />
          <span className="flex flex-col gap-0.5">
            <span className="font-medium">{t("emails.rejectEmail")}</span>
            <span className="text-xs text-muted-foreground">
              {t("emails.rejectEmailHint")}
            </span>
          </span>
        </label>
        {withEmail ? (
          draft.isPending ? (
            <p role="status" className="text-xs text-muted-foreground">
              {t("emails.loadingDraft")}
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label htmlFor={ids.when} className="text-xs font-medium">
                  {t("emails.when")}
                </label>
                <ChoiceSelect
                  id={ids.when}
                  value={when}
                  onChange={setWhen}
                  choices={(["now", "tomorrow", "inThreeDays"] as const).map(
                    (value) => ({ value, label: t(`emails.${value}`) })
                  )}
                />
              </div>
              <details className="text-sm">
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
                  {subject}
                </summary>
                <div className="mt-2 flex flex-col gap-2">
                  <label htmlFor={ids.subject} className="sr-only">
                    {t("emails.subject")}
                  </label>
                  <Input
                    id={ids.subject}
                    value={subject}
                    onChange={(event) => setSubject(event.target.value)}
                    maxLength={200}
                  />
                  <label htmlFor={ids.body} className="sr-only">
                    {t("emails.body")}
                  </label>
                  <Textarea
                    id={ids.body}
                    lang={draft.data?.language}
                    value={body}
                    onChange={(event) => setBody(event.target.value)}
                    rows={8}
                    maxLength={5000}
                    className="text-[13px] leading-relaxed"
                  />
                </div>
              </details>
            </div>
          )
        ) : null}
      </div>

      <AlertDialogFooter>
        <AlertDialogCancel type="button">
          {t("board.reject.cancel")}
        </AlertDialogCancel>
        <Button type="submit" variant="destructive">
          {t("board.reject.confirm")}
        </Button>
      </AlertDialogFooter>
    </form>
  )
}
