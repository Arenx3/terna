import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import { CircleAlertIcon, LockIcon, ScrollTextIcon } from "lucide-react"
import { useId, type ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import {
  AUDIT_AREAS,
  auditQuery,
  type AuditArea,
  type AuditEvent,
  type AuditFilters,
} from "@/api/audit"
import { membersQuery, type Role } from "@/api/team"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { BrandMark } from "@/components/brand"
import { ChoiceSelect } from "@/components/choice-select"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { initials } from "@/lib/format"
import { fillSlots } from "@/lib/slots"

const ALL = "all" as const

/** Midnight of a yyyy-mm-dd date in the reader's time zone, as an ISO instant. */
function startOfDay(date: string, plusDays = 0) {
  const [year, month, day] = date.split("-").map(Number)
  return new Date(year, month - 1, day + plusDays).toISOString()
}

function isArea(value: string | null): value is AuditArea {
  return AUDIT_AREAS.some((area) => area === value)
}

export function AuditPage() {
  const { t } = useTranslation()
  const { session } = useSession()
  const { isAdmin } = useRole()
  const [params, setParams] = useSearchParams()
  const companyId = session?.company.id ?? ""
  useDocumentTitle(t("audit.title"))

  const area = params.get("area")
  const actor = params.get("actor") ?? ""
  const since = params.get("since") ?? ""
  const until = params.get("until") ?? ""
  const filters: AuditFilters = {
    area: isArea(area) ? area : undefined,
    actor: actor || undefined,
    since: since ? startOfDay(since) : undefined,
    until: until ? startOfDay(until, 1) : undefined,
  }
  const filtered = Object.values(filters).some(Boolean)

  const log = useInfiniteQuery({
    ...auditQuery(companyId, filters),
    enabled: isAdmin,
  })
  const members = useQuery({ ...membersQuery(companyId), enabled: isAdmin })

  function setFilter(name: string, value: string) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value && value !== ALL) next.set(name, value)
        else next.delete(name)
        return next
      },
      { replace: true }
    )
  }

  if (!isAdmin) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <LockIcon aria-hidden="true" className="size-4" />
        {t("audit.adminOnly")}
      </p>
    )
  }

  const events = log.data?.pages.flatMap((page) => page.results) ?? []

  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.03em]">
          {t("audit.title")}
        </h1>
        <p className="text-pretty text-muted-foreground">
          {t("audit.description", { company: session?.company.name })}
        </p>
      </div>

      <search
        aria-label={t("audit.filters")}
        className="flex flex-wrap items-end gap-3"
      >
        <FilterField label={t("audit.activity")}>
          {(id) => (
            <ChoiceSelect
              id={id}
              value={isArea(area) ? area : ALL}
              onChange={(value) => setFilter("area", value)}
              choices={([ALL, ...AUDIT_AREAS] as const).map((value) => ({
                value,
                label: t(`audit.areas.${value}`),
              }))}
              className="w-44"
            />
          )}
        </FilterField>
        <FilterField label={t("audit.person")}>
          {(id) => (
            <ChoiceSelect
              id={id}
              value={actor || ALL}
              onChange={(value) => setFilter("actor", value)}
              choices={[
                { value: ALL, label: t("audit.everyone") },
                ...(members.data ?? []).map((member) => ({
                  value: member.user.id,
                  label: member.user.full_name,
                })),
              ]}
              className="w-52"
            />
          )}
        </FilterField>
        <FilterField label={t("audit.since")}>
          {(id) => (
            <Input
              id={id}
              type="date"
              value={since}
              max={until || undefined}
              onChange={(event) => setFilter("since", event.target.value)}
              className="w-40"
            />
          )}
        </FilterField>
        <FilterField label={t("audit.until")}>
          {(id) => (
            <Input
              id={id}
              type="date"
              value={until}
              min={since || undefined}
              onChange={(event) => setFilter("until", event.target.value)}
              className="w-40"
            />
          )}
        </FilterField>
        {filtered ? (
          <Button
            variant="ghost"
            onClick={() => setParams({}, { replace: true })}
          >
            {t("audit.clear")}
          </Button>
        ) : null}
      </search>

      {log.isPending ? (
        <LogSkeleton />
      ) : log.isError ? (
        <div
          role="alert"
          className="flex items-center gap-3 rounded-xl border px-5 py-4 text-sm"
        >
          <CircleAlertIcon
            aria-hidden="true"
            className="size-4 text-destructive"
          />
          <span className="flex-1">{t("audit.loadError")}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void log.refetch()}
          >
            {t("audit.retry")}
          </Button>
        </div>
      ) : events.length === 0 ? (
        <Empty className="rounded-xl border border-dashed py-14">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <ScrollTextIcon aria-hidden="true" />
            </EmptyMedia>
            <EmptyDescription>
              {filtered ? t("audit.emptyFiltered") : t("audit.empty")}
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="flex flex-col gap-6">
          {groupByDay(events).map(([day, entries]) => (
            <DaySection key={day} day={day} entries={entries} />
          ))}
          {log.hasNextPage ? (
            <Button
              variant="outline"
              className="self-start"
              disabled={log.isFetchingNextPage}
              onClick={() => void log.fetchNextPage()}
            >
              {log.isFetchingNextPage
                ? t("audit.loadingMore")
                : t("audit.loadMore")}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  )
}

function FilterField({
  label,
  children,
}: {
  label: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      {children(id)}
    </div>
  )
}

/** Entries grouped by the reader's local day, newest first. */
function groupByDay(events: AuditEvent[]): [string, AuditEvent[]][] {
  const days = new Map<string, AuditEvent[]>()
  for (const event of events) {
    const date = new Date(event.occurred_at)
    const day = `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`
    days.set(day, [...(days.get(day) ?? []), event])
  }
  return [...days.entries()]
}

function DaySection({ day, entries }: { day: string; entries: AuditEvent[] }) {
  const { i18n } = useTranslation()
  const headingId = useId()
  const [year, month, date] = day.split("-").map(Number)
  const value = new Date(year, month - 1, date)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const daysAgo = Math.round((today.getTime() - value.getTime()) / 86_400_000)
  const label =
    daysAgo <= 1
      ? new Intl.RelativeTimeFormat(i18n.language, { numeric: "auto" }).format(
          -daysAgo,
          "day"
        )
      : new Intl.DateTimeFormat(i18n.language, {
          weekday: "long",
          day: "numeric",
          month: "long",
          year: year === today.getFullYear() ? undefined : "numeric",
        }).format(value)

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <h2
        id={headingId}
        className="font-sans text-xs font-medium text-muted-foreground first-letter:uppercase"
      >
        {label}
      </h2>
      <ol className="divide-y overflow-hidden rounded-xl border bg-card">
        {entries.map((entry) => (
          <Entry key={entry.id} entry={entry} />
        ))}
      </ol>
    </section>
  )
}

function Entry({ entry }: { entry: AuditEvent }) {
  const { t, i18n } = useTranslation()
  const payload = (entry.payload ?? {}) as Record<string, string>
  const role = (value?: string) =>
    value ? t(`roles.${value as Role}`).toLowerCase() : ""
  const sentence = t(`audit.events.${entry.type}`, {
    role: role(payload.role),
    from: role(payload.from),
    to: role(payload.to),
  })
  const actor = entry.actor_name || t("audit.system")
  const time = new Intl.DateTimeFormat(i18n.language, {
    timeStyle: "short",
  }).format(new Date(entry.occurred_at))

  return (
    <li className="flex items-start gap-3 px-5 py-3.5">
      {entry.actor_name ? (
        <span
          aria-hidden="true"
          className="mt-px grid size-6 shrink-0 place-items-center rounded-full border bg-muted text-[10px] font-medium"
        >
          {initials(entry.actor_name)}
        </span>
      ) : (
        <BrandMark className="mt-1 size-4 shrink-0" />
      )}
      <p className="min-w-0 flex-1 text-sm leading-6 text-muted-foreground">
        {fillSlots(sentence, {
          actor: <span className="font-medium text-foreground">{actor}</span>,
          subject: (
            <span className="font-medium break-words text-foreground">
              {entry.entity_label}
            </span>
          ),
        })}
      </p>
      <time
        dateTime={entry.occurred_at}
        className="shrink-0 pt-0.5 font-mono text-xs text-faint-foreground tabular-nums"
      >
        {time}
      </time>
    </li>
  )
}

function LogSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex flex-col gap-2"
    >
      <Skeleton className="h-3 w-24" />
      <div className="divide-y rounded-xl border">
        {[0, 1, 2, 3, 4].map((row) => (
          <div key={row} className="flex items-center gap-3 px-5 py-4">
            <Skeleton className="size-6 rounded-full" />
            <Skeleton className="h-3.5 w-80" />
            <Skeleton className="ml-auto h-3 w-10" />
          </div>
        ))}
      </div>
    </div>
  )
}
