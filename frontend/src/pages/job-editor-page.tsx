import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeftIcon,
  CheckIcon,
  CircleAlertIcon,
  CircleCheckIcon,
  CircleIcon,
  EllipsisIcon,
  ExternalLinkIcon,
  LockIcon,
} from "lucide-react"
import {
  useEffect,
  useId,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react"
import { useTranslation } from "react-i18next"
import {
  Link,
  useBlocker,
  useLocation,
  useNavigate,
  useParams,
} from "react-router"

import type { Schemas } from "@/api/client"
import { ApiError, errorMessage } from "@/api/errors"
import {
  closeJob,
  createJob,
  deleteJob,
  EMPLOYMENTS,
  jobQuery,
  pipelineTemplateQuery,
  publishJob,
  updateJob,
  WORKPLACES,
  COUNTRIES,
  type Country,
  type Employment,
  type Job,
  type JobInput,
  type Stage,
  type Workplace,
} from "@/api/jobs"
import { currentCompanyQuery } from "@/api/careers"
import { membersQuery } from "@/api/team"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { ChoiceSelect } from "@/components/choice-select"
import { JobStatusBadge } from "@/components/jobs/job-status-badge"
import { JobTabs } from "@/components/jobs/job-tabs"
import {
  RequirementsEditor,
  type DraftRequirement,
} from "@/components/jobs/requirements-editor"
import { StagesEditor, type DraftStage } from "@/components/jobs/stages-editor"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { countryName, shortDate } from "@/lib/format"
import { cn } from "@/lib/utils"

type Language = Schemas["LanguageEnum"]
type Currency = Schemas["SalaryCurrencyEnum"]
type Period = Schemas["SalaryPeriodEnum"]

type Draft = {
  title: string
  department: string
  location: string
  country: Country
  workplace: Workplace
  employment: Employment
  language: Language
  description: string
  salary_min: string
  salary_max: string
  salary_currency: Currency
  salary_period: Period
  owner: string
  requirements: DraftRequirement[]
  stages: DraftStage[]
}

const NO_OWNER = "none"

function fromStages(stages: Stage[]): DraftStage[] {
  return stages.map((stage, index) => ({
    key: stage.id ? `stage-${stage.id}` : `stage-new-${index}`,
    id: stage.id,
    name: stage.name,
    kind: stage.kind,
  }))
}

function fromJob(job: Job): Draft {
  return {
    title: job.title,
    department: job.department ?? "",
    location: job.location ?? "",
    country: job.country ?? "MX",
    workplace: job.workplace ?? "onsite",
    employment: job.employment ?? "full_time",
    language: job.language ?? "es",
    description: job.description ?? "",
    salary_min: job.salary_min?.toString() ?? "",
    salary_max: job.salary_max?.toString() ?? "",
    salary_currency: job.salary_currency ?? "MXN",
    salary_period: job.salary_period ?? "month",
    owner: job.hiring_manager?.id ?? NO_OWNER,
    requirements: (job.requirements ?? []).map((item) => ({
      key: `req-${item.id}`,
      id: item.id,
      text: item.text,
      kind: item.kind,
    })),
    stages: fromStages(job.stages ?? []),
  }
}

function blankDraft(stages: Stage[], language: Language): Draft {
  return {
    title: "",
    department: "",
    location: "",
    country: "MX",
    workplace: "onsite",
    employment: "full_time",
    language,
    description: "",
    salary_min: "",
    salary_max: "",
    salary_currency: "MXN",
    salary_period: "month",
    owner: NO_OWNER,
    requirements: [],
    // A new job never reuses template row ids.
    stages: fromStages(stages.map((stage) => ({ ...stage, id: null }))),
  }
}

function amount(value: string) {
  const digits = value.replace(/[^\d]/g, "")
  return digits ? Number(digits) : null
}

function toInput(draft: Draft): JobInput {
  return {
    title: draft.title.trim(),
    department: draft.department.trim(),
    location: draft.location.trim(),
    country: draft.country,
    workplace: draft.workplace,
    employment: draft.employment,
    language: draft.language,
    description: draft.description.trim(),
    salary_min: amount(draft.salary_min),
    salary_max: amount(draft.salary_max),
    salary_currency: draft.salary_currency,
    salary_period: draft.salary_period,
    hiring_manager_id: draft.owner === NO_OWNER ? null : draft.owner,
    requirements: draft.requirements
      .filter((item) => item.text.trim())
      .map((item) => ({
        id: item.id ?? null,
        text: item.text.trim(),
        kind: item.kind,
      })),
    stages: draft.stages.map((stage) => ({
      id: stage.id ?? null,
      name: stage.name.trim(),
      kind: stage.kind,
    })),
  }
}

const fingerprint = (draft: Draft) => JSON.stringify(toInput(draft))

/** Field messages from the API, without the nested per-item objects. */
function messages(error: unknown, field: string): string[] {
  if (!(error instanceof ApiError)) return []
  return (error.fields[field] ?? []).filter(
    (text) => !text.startsWith("[object")
  )
}

export function JobEditorPage() {
  const { t, i18n } = useTranslation()
  const { jobId } = useParams()
  const { session } = useSession()
  const { canSeeJobs, canManageJobs } = useRole()
  const companyId = session?.company.id ?? ""
  const isNew = jobId === undefined

  const job = useQuery({
    ...jobQuery(companyId, jobId ?? ""),
    enabled: !isNew && canSeeJobs,
  })
  const template = useQuery({
    ...pipelineTemplateQuery(companyId),
    enabled: isNew && canManageJobs,
  })

  useDocumentTitle(
    isNew ? t("jobs.editor.newTitle") : (job.data?.title ?? t("jobs.title"))
  )

  if (!canSeeJobs || (isNew && !canManageJobs)) {
    return <Notice icon={<LockIcon />} text={t("jobs.forbidden.description")} />
  }
  if (isNew ? template.isPending : job.isPending) return <EditorSkeleton />
  if (!isNew && job.isError) {
    return (
      <Notice icon={<CircleAlertIcon />} text={t("jobs.editor.notFound")} />
    )
  }
  if (isNew && template.isError) {
    return <Notice icon={<CircleAlertIcon />} text={t("jobs.loadError")} />
  }

  const language: Language = i18n.resolvedLanguage === "en" ? "en" : "es"
  return (
    <JobEditor
      key={job.data?.id ?? "new"}
      job={job.data}
      initial={
        job.data
          ? fromJob(job.data)
          : blankDraft(template.data?.stages ?? [], language)
      }
      readOnly={!canManageJobs}
    />
  )
}

type Action = "save" | "publish" | "close"

function JobEditor({
  job,
  initial,
  readOnly,
}: {
  job?: Job
  initial: Draft
  readOnly: boolean
}) {
  const { t, i18n } = useTranslation()
  const { session } = useSession()
  const companyId = session?.company.id ?? ""
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const formId = useId()
  const errorsId = useId()

  const [baseline, setBaseline] = useState(initial)
  const [draft, setDraft] = useState(initial)
  const location = useLocation()
  // A job just created on /jobs/new arrives here with its confirmation.
  const [notice, setNotice] = useState<string | null>(
    (location.state as { notice?: string } | null)?.notice ?? null
  )
  const [confirmDelete, setConfirmDelete] = useState(false)
  const leaving = useRef(false)

  const dirty = fingerprint(draft) !== fingerprint(baseline)
  const members = useQuery({ ...membersQuery(companyId), enabled: !readOnly })
  const company = useQuery(currentCompanyQuery(companyId))

  function edit(patch: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...patch }))
    setNotice(null)
  }

  function remember(saved: Job) {
    queryClient.setQueryData(jobQuery(companyId, saved.id).queryKey, saved)
    void queryClient.invalidateQueries({
      queryKey: ["jobs", companyId, "list"],
    })
    const next = fromJob(saved)
    setBaseline(next)
    setDraft(next)
  }

  const mustHaves = draft.requirements.filter(
    (item) => item.kind === "must" && item.text.trim()
  ).length
  const niceToHaves = draft.requirements.filter(
    (item) => item.kind === "nice" && item.text.trim()
  ).length
  // A job created by a run whose next step failed: later runs update it instead.
  const created = useRef<Job | undefined>(undefined)

  const run = useMutation({
    mutationFn: async (action: Action) => {
      if (action === "publish" && mustHaves === 0) {
        // Same rule as the API, checked first so nothing half-happens.
        throw new ApiError(409, { code: "publish_needs_must_have" })
      }
      let saved = job ?? created.current
      if (!saved || dirty) {
        const input = toInput(draft)
        saved = saved
          ? await updateJob(saved.id, input)
          : await createJob(input)
        created.current = job ? undefined : saved
        remember(saved)
      }
      if (action === "publish") saved = await publishJob(saved.id)
      if (action === "close") saved = await closeJob(saved.id)
      return saved
    },
    onSuccess: (saved) => {
      remember(saved)
      setNotice(t("jobs.editor.saved"))
    },
    onSettled: (_data, error) => {
      const saved = created.current
      if (!job && saved) {
        leaving.current = true
        void navigate(`/jobs/${saved.id}`, {
          replace: true,
          state: error ? null : { notice: t("jobs.editor.saved") },
        })
      }
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteJob(job?.id ?? ""),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["jobs", companyId, "list"],
      })
      leaving.current = true
      void navigate("/jobs")
    },
  })

  // Leaving with unsaved changes asks first, inside the app and on reload.
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      !leaving.current &&
      currentLocation.pathname !== nextLocation.pathname
  )
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [dirty])

  const error = run.error ?? remove.error
  const fieldError = (field: string) => messages(error, field)
  const requirementsInvalid =
    error instanceof ApiError && "requirements" in error.fields
  const status = job?.status ?? "draft"
  const busy = run.isPending || remove.isPending

  const ownerChoices = [
    { value: NO_OWNER, label: t("jobs.noOwner") },
    ...(members.data ?? [])
      .filter((member) => member.role !== "interviewer")
      .map((member) => ({
        value: member.user.id,
        label: member.user.full_name,
      })),
  ]
  // Hiring managers can't list the team; show the current owner by name.
  if (
    job?.hiring_manager &&
    !ownerChoices.some((c) => c.value === job.hiring_manager?.id)
  ) {
    ownerChoices.push({
      value: job.hiring_manager.id,
      label: job.hiring_manager.full_name,
    })
  }

  const dates = [
    job?.created_at
      ? t("jobs.editor.created", {
          date: shortDate(job.created_at, i18n.language),
        })
      : null,
    job?.published_at
      ? t("jobs.editor.published", {
          date: shortDate(job.published_at, i18n.language),
        })
      : null,
    job?.closed_at
      ? t("jobs.editor.closed", {
          date: shortDate(job.closed_at, i18n.language),
        })
      : null,
  ].filter(Boolean)

  const generalError = error ? errorMessage(t, error) : null
  const stageErrors = fieldError("stages")

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <Link
          to="/jobs"
          className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <ArrowLeftIcon aria-hidden="true" className="size-4" />
          {t("jobs.editor.back")}
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h1 className="min-w-0 text-[28px] leading-tight font-semibold tracking-[-0.03em] break-words">
                {draft.title.trim() ||
                  (job ? t("jobs.editor.untitled") : t("jobs.editor.newTitle"))}
              </h1>
              <JobStatusBadge status={status} />
            </div>
            {dates.length > 0 ? (
              <p className="text-[13px] text-faint-foreground">
                {dates.join(" · ")}
              </p>
            ) : null}
          </div>

          {readOnly ? null : (
            <div className="flex items-center gap-2">
              <span role="status" className="text-[13px] text-muted-foreground">
                {notice && !dirty ? (
                  <span className="inline-flex items-center gap-1.5">
                    <CheckIcon
                      aria-hidden="true"
                      className="size-3.5 text-success"
                    />
                    {notice}
                  </span>
                ) : null}
              </span>
              {status === "open" ? (
                <Button type="submit" form={formId} disabled={busy || !dirty}>
                  {run.isPending
                    ? t("jobs.editor.saving")
                    : t("jobs.editor.save")}
                </Button>
              ) : (
                <>
                  <Button
                    type="submit"
                    form={formId}
                    variant="outline"
                    disabled={busy || (Boolean(job) && !dirty)}
                  >
                    {run.isPending && run.variables === "save"
                      ? t("jobs.editor.saving")
                      : job && status === "closed"
                        ? t("jobs.editor.save")
                        : t("jobs.editor.saveDraft")}
                  </Button>
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() => run.mutate("publish")}
                  >
                    {run.isPending && run.variables === "publish"
                      ? t("jobs.editor.publishing")
                      : status === "closed"
                        ? t("jobs.editor.reopen")
                        : t("jobs.editor.publish")}
                  </Button>
                </>
              )}
              {job && status === "open" && company.data ? (
                <a
                  href={`/careers/${company.data.slug}/jobs/${job.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className={buttonVariants({ variant: "ghost" })}
                >
                  <ExternalLinkIcon
                    data-icon="inline-start"
                    aria-hidden="true"
                  />
                  {t("jobs.editor.viewPosting")}
                </a>
              ) : null}
              {job && status !== "closed" ? (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={t("jobs.editor.more")}
                        disabled={busy}
                      />
                    }
                  >
                    <EllipsisIcon aria-hidden="true" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="min-w-44">
                    {status === "open" ? (
                      <DropdownMenuItem onClick={() => run.mutate("close")}>
                        {t("jobs.editor.close")}
                      </DropdownMenuItem>
                    ) : (
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => setConfirmDelete(true)}
                      >
                        {t("jobs.editor.delete")}
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </div>
          )}
        </div>

        {job ? <JobTabs jobId={job.id} /> : null}

        {readOnly ? (
          <p className="flex items-center gap-2 rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <LockIcon aria-hidden="true" className="size-4 shrink-0" />
            {t("jobs.editor.readOnly")}
          </p>
        ) : null}
        {generalError ? (
          <Alert variant="destructive" id={errorsId}>
            <CircleAlertIcon aria-hidden="true" />
            <AlertDescription>{generalError}</AlertDescription>
          </Alert>
        ) : null}
      </header>

      <div
        className={cn(
          "grid items-start gap-8",
          !readOnly && "lg:grid-cols-[minmax(0,1fr)_17rem]"
        )}
      >
        <div className="flex min-w-0 flex-col gap-6">
          <Section
            title={t("jobs.editor.details")}
            hint={t("jobs.editor.detailsHint")}
          >
            <form
              id={formId}
              onSubmit={(event) => {
                event.preventDefault()
                run.mutate("save")
              }}
            >
              <fieldset
                disabled={readOnly}
                className="grid gap-5 sm:grid-cols-6"
              >
                <TextInput
                  className="sm:col-span-6"
                  label={t("jobs.editor.title")}
                  value={draft.title}
                  onChange={(title) => edit({ title })}
                  placeholder={t("jobs.editor.titlePlaceholder")}
                  errors={fieldError("title")}
                  required
                  maxLength={160}
                />
                <TextInput
                  className="sm:col-span-2"
                  label={t("jobs.editor.department")}
                  value={draft.department}
                  onChange={(department) => edit({ department })}
                  placeholder={t("jobs.editor.departmentPlaceholder")}
                  maxLength={120}
                />
                <TextInput
                  className="sm:col-span-2"
                  label={t("jobs.editor.location")}
                  value={draft.location}
                  onChange={(location) => edit({ location })}
                  placeholder={t("jobs.editor.locationPlaceholder")}
                  maxLength={160}
                />
                <SelectInput
                  className="sm:col-span-2"
                  label={t("jobs.editor.country")}
                  value={draft.country}
                  onChange={(country) => edit({ country })}
                  choices={COUNTRIES.map((value) => ({
                    value,
                    label: countryName(value, i18n.language),
                  }))}
                  disabled={readOnly}
                />
                <SelectInput
                  className="sm:col-span-2"
                  label={t("jobs.editor.workplace")}
                  value={draft.workplace}
                  onChange={(workplace) => edit({ workplace })}
                  choices={WORKPLACES.map((value) => ({
                    value,
                    label: t(`jobs.workplace.${value}`),
                  }))}
                  disabled={readOnly}
                />
                <SelectInput
                  className="sm:col-span-2"
                  label={t("jobs.editor.employment")}
                  value={draft.employment}
                  onChange={(employment) => edit({ employment })}
                  choices={EMPLOYMENTS.map((value) => ({
                    value,
                    label: t(`jobs.employment.${value}`),
                  }))}
                  disabled={readOnly}
                />
                <SelectInput
                  className="sm:col-span-2"
                  label={t("jobs.editor.language")}
                  value={draft.language}
                  onChange={(language) => edit({ language })}
                  choices={(["es", "en"] as const).map((value) => ({
                    value,
                    label: t(`language.${value}`),
                  }))}
                  disabled={readOnly}
                />

                <FieldSet className="sm:col-span-6">
                  <FieldLegend variant="label">
                    {t("jobs.editor.salary")}
                  </FieldLegend>
                  <div className="grid gap-3 sm:grid-cols-4">
                    <TextInput
                      label={t("jobs.editor.salaryMin")}
                      value={draft.salary_min}
                      onChange={(salary_min) => edit({ salary_min })}
                      inputMode="numeric"
                      autoComplete="off"
                      errors={fieldError("salary_min")}
                    />
                    <TextInput
                      label={t("jobs.editor.salaryMax")}
                      value={draft.salary_max}
                      onChange={(salary_max) => edit({ salary_max })}
                      inputMode="numeric"
                      autoComplete="off"
                      errors={fieldError("salary_max")}
                    />
                    <SelectInput
                      label={t("jobs.editor.currency")}
                      value={draft.salary_currency}
                      onChange={(salary_currency) => edit({ salary_currency })}
                      choices={(["MXN", "USD"] as const).map((value) => ({
                        value,
                        label: value,
                      }))}
                      disabled={readOnly}
                    />
                    <SelectInput
                      label={t("jobs.editor.period")}
                      value={draft.salary_period}
                      onChange={(salary_period) => edit({ salary_period })}
                      choices={(["month", "year"] as const).map((value) => ({
                        value,
                        label: t(`jobs.editor.periods.${value}`),
                      }))}
                      disabled={readOnly}
                    />
                  </div>
                  <FieldDescription>
                    {t("jobs.editor.salaryHint")}
                  </FieldDescription>
                </FieldSet>

                <SelectInput
                  className="sm:col-span-3"
                  label={t("jobs.editor.owner")}
                  hint={t("jobs.editor.ownerHint")}
                  value={draft.owner}
                  onChange={(owner) => edit({ owner })}
                  choices={ownerChoices}
                  errors={fieldError("hiring_manager_id")}
                  disabled={readOnly}
                />

                <Field className="sm:col-span-6">
                  <DescriptionInput
                    value={draft.description}
                    onChange={(description) => edit({ description })}
                    errors={fieldError("description")}
                  />
                </Field>
              </fieldset>
            </form>
          </Section>

          <Section
            title={t("jobs.editor.requirements")}
            hint={t("jobs.editor.requirementsHint")}
            meta={
              <span className="text-[13px] text-muted-foreground tabular-nums">
                {t("jobs.mustCount", { count: mustHaves })}
                <span className="text-faint-foreground">
                  {" · "}
                  {t("jobs.niceCount", { count: niceToHaves })}
                </span>
              </span>
            }
          >
            <RequirementsEditor
              value={draft.requirements}
              onChange={(requirements) => edit({ requirements })}
              disabled={readOnly}
              invalid={requirementsInvalid}
            />
            {requirementsInvalid ? (
              <p className="mt-3 text-sm text-destructive">
                {t("jobs.editor.checkRequirements")}
              </p>
            ) : null}
          </Section>

          <Section
            title={t("jobs.editor.stages")}
            hint={t("jobs.editor.stagesHint")}
          >
            <StagesEditor
              value={draft.stages}
              onChange={(stages) => edit({ stages })}
              disabled={readOnly}
            />
            {stageErrors.map((message) => (
              <p key={message} className="mt-3 text-sm text-destructive">
                {message}
              </p>
            ))}
          </Section>
        </div>

        {readOnly ? null : (
          <aside className="flex flex-col gap-4 rounded-xl border bg-card p-5 lg:sticky lg:top-20">
            <h2 className="text-sm font-semibold">
              {t("jobs.editor.checklist.title")}
            </h2>
            <ul className="flex flex-col gap-2.5 text-sm">
              <Check
                done={Boolean(draft.title.trim())}
                label={t("jobs.editor.checklist.name")}
              />
              <Check
                done={mustHaves > 0}
                label={t("jobs.editor.checklist.must")}
              />
              <Check
                done={Boolean(draft.description.trim())}
                label={t("jobs.editor.checklist.description")}
                optional
              />
              <Check
                done={draft.owner !== NO_OWNER}
                label={t("jobs.editor.checklist.owner")}
                optional
              />
            </ul>
          </aside>
        )}
      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("jobs.editor.deleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("jobs.editor.deleteDescription", {
                title: job?.title || t("jobs.editor.untitled"),
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("jobs.editor.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => remove.mutate()}
            >
              {t("jobs.editor.delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={blocker.state === "blocked"}
        onOpenChange={(open) => {
          if (!open && blocker.state === "blocked") blocker.reset()
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("jobs.editor.leaveTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("jobs.editor.leaveDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("jobs.editor.stay")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => blocker.state === "blocked" && blocker.proceed()}
            >
              {t("jobs.editor.leave")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function Section({
  title,
  hint,
  meta,
  children,
}: {
  title: string
  hint: string
  meta?: ReactNode
  children: ReactNode
}) {
  const id = useId()
  return (
    <section
      aria-labelledby={id}
      className="rounded-xl border bg-card p-5 sm:p-6"
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-x-6 gap-y-1">
        <div className="flex max-w-xl flex-col gap-1">
          <h2 id={id} className="text-base font-semibold tracking-[-0.01em]">
            {title}
          </h2>
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            {hint}
          </p>
        </div>
        {meta}
      </div>
      {children}
    </section>
  )
}

function TextInput({
  label,
  value,
  onChange,
  errors = [],
  className,
  ...props
}: {
  label: string
  value: string
  onChange: (value: string) => void
  errors?: string[]
  className?: string
} & Omit<ComponentProps<typeof Input>, "value" | "onChange" | "id">) {
  const id = useId()
  const invalid = errors.length > 0
  return (
    <Field data-invalid={invalid || undefined} className={className}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? `${id}-error` : undefined}
        {...props}
      />
      <FieldError
        id={`${id}-error`}
        errors={errors.map((message) => ({ message }))}
      />
    </Field>
  )
}

function SelectInput<T extends string>({
  label,
  hint,
  value,
  onChange,
  choices,
  errors = [],
  disabled,
  className,
}: {
  label: string
  hint?: string
  value: T
  onChange: (value: T) => void
  choices: { value: T; label: string }[]
  errors?: string[]
  disabled?: boolean
  className?: string
}) {
  const id = useId()
  const invalid = errors.length > 0
  const describedBy =
    [hint ? `${id}-hint` : null, invalid ? `${id}-error` : null]
      .filter(Boolean)
      .join(" ") || undefined
  return (
    <Field data-invalid={invalid || undefined} className={className}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <ChoiceSelect
        id={id}
        value={value}
        onChange={onChange}
        choices={choices}
        disabled={disabled}
        invalid={invalid}
        describedBy={describedBy}
      />
      {hint ? (
        <FieldDescription id={`${id}-hint`}>{hint}</FieldDescription>
      ) : null}
      <FieldError
        id={`${id}-error`}
        errors={errors.map((message) => ({ message }))}
      />
    </Field>
  )
}

function DescriptionInput({
  value,
  onChange,
  errors,
}: {
  value: string
  onChange: (value: string) => void
  errors: string[]
}) {
  const { t } = useTranslation()
  const id = useId()
  const invalid = errors.length > 0
  return (
    <>
      <FieldLabel htmlFor={id}>{t("jobs.editor.description")}</FieldLabel>
      <Textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={7}
        maxLength={20000}
        aria-invalid={invalid || undefined}
        aria-describedby={`${id}-hint`}
        className="min-h-40 leading-relaxed"
      />
      <FieldDescription id={`${id}-hint`}>
        {t("jobs.editor.descriptionHint")}
      </FieldDescription>
      <FieldError errors={errors.map((message) => ({ message }))} />
    </>
  )
}

function Check({
  done,
  label,
  optional = false,
}: {
  done: boolean
  label: string
  optional?: boolean
}) {
  const { t } = useTranslation()
  const Icon = done ? CircleCheckIcon : CircleIcon
  return (
    <li className="flex items-start gap-2.5">
      <Icon
        aria-hidden="true"
        className={cn(
          "mt-0.5 size-4 shrink-0",
          done ? "text-success" : "text-faint-foreground"
        )}
      />
      <span className="flex flex-col">
        <span className={done ? "text-foreground" : "text-muted-foreground"}>
          {label}
          <span className="sr-only">
            {" "}
            {done
              ? t("jobs.editor.checklist.done")
              : t("jobs.editor.checklist.missing")}
          </span>
        </span>
        {optional ? (
          <span className="text-xs text-faint-foreground">
            {t("jobs.editor.checklist.recommended")}
          </span>
        ) : null}
      </span>
    </li>
  )
}

function Notice({ icon, text }: { icon: ReactNode; text: string }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-start gap-4">
      <Link
        to="/jobs"
        className="inline-flex items-center gap-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <ArrowLeftIcon aria-hidden="true" className="size-4" />
        {t("jobs.editor.back")}
      </Link>
      <p className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm text-muted-foreground [&_svg]:size-4">
        {icon}
        {text}
      </p>
    </div>
  )
}

function EditorSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex flex-col gap-8"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-8 w-72" />
      </div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="flex flex-col gap-6">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
        </div>
        <Skeleton className="h-44 rounded-xl" />
      </div>
    </div>
  )
}
