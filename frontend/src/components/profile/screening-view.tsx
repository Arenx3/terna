import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CheckIcon,
  CircleAlertIcon,
  FileSearchIcon,
  RotateCwIcon,
} from "lucide-react"
import { useId, type ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { errorMessage } from "@/api/errors"
import {
  isScreening,
  rerunScreening,
  screeningQuery,
  type RequirementResult,
  type Screening,
  type Verdict,
} from "@/api/screening"
import { useSession } from "@/auth/session"
import { MarkedText } from "@/components/screening/marked-text"
import {
  VERDICT_FILL,
  VerdictMeter,
} from "@/components/screening/verdict-meter"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { relativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

/** A requirement's evidence, to highlight where it sits in the résumé's text. */
export type Highlight = {
  requirement: string
  passages: Record<number, number[][]>
}

const VERDICTS: Verdict[] = ["meets", "partial", "no_evidence"]

/**
 * The screening: every requirement of the job with its verdict and the lines
 * of the résumé behind it, highlighted. A suggestion with its reasons shown,
 * never a score to trust blindly.
 */
export function ScreeningView({
  applicationId,
  canManage,
  onShowInResume,
}: {
  applicationId: number
  canManage: boolean
  /** Open the résumé's text with this requirement's evidence highlighted. */
  onShowInResume: (highlight: Highlight) => void
}) {
  const { t } = useTranslation()
  const { session } = useSession()
  const companyId = session?.company.id ?? ""
  const queryClient = useQueryClient()
  const query = screeningQuery(companyId, applicationId)
  const screening = useQuery(query)
  const rerun = useMutation({
    mutationFn: () => rerunScreening(applicationId),
    onSuccess: (data) => queryClient.setQueryData(query.queryKey, data),
  })

  if (screening.isPending) return <ScreeningSkeleton />
  if (screening.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t("screening.loadError")}
      </p>
    )
  }

  const data = screening.data
  const again = canManage ? (
    <Button
      variant={data.status === "failed" ? "outline" : "ghost"}
      size="sm"
      disabled={rerun.isPending || isScreening(data)}
      onClick={() => rerun.mutate()}
    >
      <RotateCwIcon data-icon="inline-start" aria-hidden="true" />
      {data.status === "failed" ? t("screening.retry") : t("screening.rerun")}
    </Button>
  ) : null
  const rerunError = rerun.isError ? (
    <p role="alert" className="text-sm text-destructive">
      {errorMessage(t, rerun.error)}
    </p>
  ) : null

  if (isScreening(data)) {
    const reading = data.status === "waiting"
    return (
      <div className="flex flex-col gap-4">
        <p
          role="status"
          className="flex items-center gap-2 text-sm text-muted-foreground"
        >
          <Spinner aria-hidden="true" />
          {reading ? t("screening.readingResume") : t("screening.running")}
        </p>
        <ScreeningSkeleton />
      </div>
    )
  }

  if (data.status === "waiting") {
    // The résumé couldn't be read: there's nothing to compare yet.
    return (
      <Alert>
        <FileSearchIcon aria-hidden="true" />
        <AlertTitle>{t("screening.noTextTitle")}</AlertTitle>
        <AlertDescription>{t("screening.noTextHint")}</AlertDescription>
      </Alert>
    )
  }

  if (data.status === "failed") {
    return (
      <div className="flex flex-col gap-3">
        <Alert variant="destructive">
          <CircleAlertIcon aria-hidden="true" />
          <AlertTitle>{t("screening.failedTitle")}</AlertTitle>
          <AlertDescription>
            <p>{t("screening.failedHint")}</p>
            {data.detail ? (
              <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
                {data.detail}
              </p>
            ) : null}
          </AlertDescription>
        </Alert>
        {again ? <div>{again}</div> : null}
        {rerunError}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <Summary data={data} action={again} />
      {rerunError}
      {KINDS.map((kind) => {
        const items = data.requirements.filter((r) => r.kind === kind)
        return items.length ? (
          <RequirementGroup
            key={kind}
            kind={kind}
            items={items}
            onShowInResume={onShowInResume}
          />
        ) : null
      })}
    </div>
  )
}

const KINDS = ["must", "nice"] as const

function Summary({ data, action }: { data: Screening; action: ReactNode }) {
  const { t, i18n } = useTranslation()
  const number = new Intl.NumberFormat(i18n.language, {
    maximumFractionDigits: 1,
  })
  return (
    <section
      aria-label={t("screening.summaryLabel")}
      className="flex flex-col gap-4 rounded-xl border bg-card p-4"
    >
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <p className="flex items-baseline gap-2">
          <span className="font-heading text-[28px] leading-none font-semibold tracking-[-0.03em] whitespace-nowrap tabular-nums">
            {t("screening.ofTotal", {
              meets: data.must_meets,
              total: data.must_total,
            })}
          </span>
          <span className="text-sm text-muted-foreground">
            {t("screening.mustMet", { count: data.must_total })}
            {data.must_partial
              ? ` · ${t("screening.partly", { count: data.must_partial })}`
              : ""}
          </span>
        </p>
        {data.nice_total ? (
          <p className="text-sm text-muted-foreground tabular-nums">
            {t("screening.niceMet", {
              meets: data.nice_meets,
              count: data.nice_total,
            })}
            {data.nice_partial
              ? ` · ${t("screening.partly", { count: data.nice_partial })}`
              : ""}
          </p>
        ) : null}
      </div>

      <VerdictMeter counts={data} size="md" />

      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-xs text-faint-foreground">
        <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-hidden="true">
          {VERDICTS.map((verdict) => (
            <li key={verdict} className="flex items-center gap-1.5">
              <span
                className={cn("h-2 w-3 rounded-[2px]", VERDICT_FILL[verdict])}
              />
              {t(`screening.verdict.${verdict}`)}
            </li>
          ))}
        </ul>
        <p className="tabular-nums">
          {t("screening.points", {
            points: number.format(data.points),
            max: number.format(data.max_points),
            must: data.weights.must,
            nice: data.weights.nice,
          })}
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
        <p className="text-xs text-pretty text-muted-foreground">
          {t("screening.disclaimer")}
          {data.completed_at ? (
            <span className="text-faint-foreground">
              {" "}
              ·{" "}
              {t("screening.completed", {
                time: relativeTime(data.completed_at, i18n.language),
              })}
            </span>
          ) : null}
        </p>
        {action}
      </div>
    </section>
  )
}

function RequirementGroup({
  kind,
  items,
  onShowInResume,
}: {
  kind: "must" | "nice"
  items: RequirementResult[]
  onShowInResume: (highlight: Highlight) => void
}) {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h3
        id={headingId}
        className="font-sans text-[11px] font-medium tracking-wider text-muted-foreground uppercase"
      >
        {t(`screening.group.${kind}`)}
      </h3>
      <ol className="flex flex-col gap-5">
        {items.map((item) => (
          <RequirementItem
            key={item.id}
            item={item}
            onShowInResume={onShowInResume}
          />
        ))}
      </ol>
    </section>
  )
}

/** The verdict at a glance. Decorative: the verdict is also written beside it. */
function VerdictGlyph({ verdict }: { verdict: Verdict | null }) {
  const base = "mt-0.5 grid size-4 shrink-0 place-items-center rounded-full"
  if (verdict === "meets") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-primary text-primary-foreground")}
      >
        <CheckIcon aria-hidden="true" className="size-3" strokeWidth={3} />
      </span>
    )
  }
  if (verdict === "partial") {
    return (
      <span
        aria-hidden="true"
        className={cn(
          base,
          "border border-primary-edge bg-[linear-gradient(90deg,var(--color-primary)_50%,transparent_50%)]"
        )}
      />
    )
  }
  if (verdict === "no_evidence") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "border border-dashed border-muted-foreground/60")}
      />
    )
  }
  return (
    <span aria-hidden="true" className={cn(base, "border border-border")} />
  )
}

function RequirementItem({
  item,
  onShowInResume,
}: {
  item: RequirementResult
  onShowInResume: (highlight: Highlight) => void
}) {
  const { t } = useTranslation()
  const verdict = item.verdict
  return (
    <li className="grid grid-cols-[1rem_1fr] gap-x-3 gap-y-2">
      <VerdictGlyph verdict={verdict} />
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <p className="text-sm font-medium text-pretty">{item.text}</p>
        <p
          className={cn(
            "text-xs whitespace-nowrap",
            verdict === "meets" ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {verdict
            ? t(`screening.verdict.${verdict}`)
            : t("screening.verdict.pending")}
        </p>
      </div>
      <div className="col-start-2 flex min-w-0 flex-col gap-2.5">
        {item.signals ? <Signals item={item} /> : null}
        {item.evidence.length ? (
          <>
            <ul className="flex flex-col gap-2">
              {item.evidence.map((evidence) => (
                <li
                  key={evidence.passage.id}
                  className="flex flex-col gap-0.5 border-l-2 border-border pl-3"
                >
                  <span className="text-[11px] text-faint-foreground">
                    {t(
                      `profile.resume.text.section.${evidence.passage.section}`
                    )}
                    {" · "}
                    <span className="font-mono tabular-nums">
                      {t("profile.resume.text.page", {
                        page: evidence.passage.page,
                      })}
                    </span>
                  </span>
                  <span className="text-sm/relaxed text-pretty text-muted-foreground">
                    <MarkedText
                      text={evidence.passage.text}
                      spans={evidence.spans}
                      draw
                    />
                  </span>
                </li>
              ))}
            </ul>
            <div>
              <Button
                variant="ghost"
                size="xs"
                className="-ml-2 text-muted-foreground"
                onClick={() =>
                  onShowInResume({
                    requirement: item.text,
                    passages: Object.fromEntries(
                      item.evidence.map((e) => [e.passage.id, e.spans])
                    ),
                  })
                }
              >
                <FileSearchIcon data-icon="inline-start" aria-hidden="true" />
                {t("screening.showInResume")}
              </Button>
            </div>
          </>
        ) : verdict === "no_evidence" ? (
          <p className="text-sm text-faint-foreground">
            {t("screening.noEvidence")}
          </p>
        ) : null}
      </div>
    </li>
  )
}

/** What each signal found, so the verdict can be checked, not taken on faith. */
function Signals({ item }: { item: RequirementResult }) {
  const { t, i18n } = useTranslation()
  const signals = item.signals
  if (!signals) return null
  const { keyword, semantic, years, level } = signals
  const number = new Intl.NumberFormat(i18n.language, {
    maximumFractionDigits: 1,
  })
  const similarity = new Intl.NumberFormat(i18n.language, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  const same = (a: string, b: string) =>
    a.localeCompare(b, undefined, { sensitivity: "base" }) === 0
  // Without evidence, the words that were looked for and not found are the point.
  const found = item.verdict === "no_evidence" ? [] : keyword.found

  return (
    <dl className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {found.length || keyword.missing.length ? (
        <div className="flex flex-wrap items-baseline gap-1.5">
          <dt className="text-faint-foreground">
            {t("screening.signal.keyword")}
          </dt>
          {found.map((term) => (
            <dd
              key={term.term}
              className="rounded-md border bg-muted px-1.5 py-px text-foreground"
            >
              {term.term}
              {same(term.term, term.matched) ? null : (
                <span className="text-muted-foreground">
                  {" "}
                  {t("screening.signal.as", { matched: term.matched })}
                </span>
              )}
            </dd>
          ))}
          {keyword.missing.map((missing) => (
            <dd
              key={missing}
              className="rounded-md border border-dashed px-1.5 py-px text-faint-foreground"
            >
              <span className="sr-only">{t("screening.signal.missing")} </span>
              {missing}
            </dd>
          ))}
        </div>
      ) : null}
      {semantic && semantic.passage !== null ? (
        <div className="flex items-baseline gap-1.5">
          <dt className="text-faint-foreground">
            {t("screening.signal.semantic")}
          </dt>
          <dd className="font-mono text-foreground tabular-nums">
            {similarity.format(semantic.score)}
          </dd>
        </div>
      ) : null}
      {years ? (
        <div className="flex items-baseline gap-1.5">
          <dt className="text-faint-foreground">
            {t("screening.signal.years")}
          </dt>
          <dd className="text-foreground tabular-nums">
            {t("screening.signal.yearsValue", {
              found: number.format(years.months / 12),
              required: years.required,
            })}
          </dd>
        </div>
      ) : null}
      {level ? (
        <div className="flex items-baseline gap-1.5">
          <dt className="text-faint-foreground">
            {t("screening.signal.level")}
          </dt>
          <dd className="text-foreground">
            {level.found
              ? t("screening.signal.levelValue", {
                  found: level.found,
                  required: level.required,
                })
              : t("screening.signal.levelUnstated", {
                  required: level.required,
                })}
          </dd>
        </div>
      ) : null}
    </dl>
  )
}

function ScreeningSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-hidden="true">
      <div className="flex flex-col gap-4 rounded-xl border p-4">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-3 w-56" />
      </div>
      {[3, 2].map((rows, group) => (
        <div key={group} className="flex flex-col gap-4">
          <Skeleton className="h-3 w-24" />
          {Array.from({ length: rows }, (_, row) => (
            <div key={row} className="grid grid-cols-[1rem_1fr] gap-3">
              <Skeleton className="size-4 rounded-full" />
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-3/5" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
