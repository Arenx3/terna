import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  PencilIcon,
  PlusIcon,
  RotateCcwIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react"
import { useDeferredValue, useId, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import { errorMessage } from "@/api/errors"
import {
  addEntry,
  deleteEntry,
  dictionaryQuery,
  saveEntry,
  type DictionaryEntry,
} from "@/api/screening"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
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
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { cn } from "@/lib/utils"

const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()

const splitAliases = (value: string) =>
  value
    .split(",")
    .map((alias) => alias.trim())
    .filter(Boolean)

/** Which entry a form is open for: a new one, or an existing term (by its key). */
type Editing = { term: string } | "new" | null

/**
 * The screening's synonyms: Terna's, and the company's own on top. A recruiter
 * teaches it the words their industry uses ("montacargas" is a forklift).
 */
export function DictionaryPage() {
  const { t } = useTranslation()
  const { session } = useSession()
  const { canSeeJobs, canManageJobs } = useRole()
  const companyId = session?.company.id ?? ""
  const queryClient = useQueryClient()
  const query = dictionaryQuery(companyId)
  const entries = useQuery({ ...query, enabled: canSeeJobs })
  // The search lives in the address, so a filtered list can be shared.
  const [params, setParams] = useSearchParams()
  const search = params.get("q") ?? ""
  const setSearch = (value: string) =>
    setParams(value ? { q: value } : {}, { replace: true })
  const deferred = useDeferredValue(search)
  const [editing, setEditing] = useState<Editing>(null)
  // Removing asks first: every open job is screened again without the entry.
  const [confirming, setConfirming] = useState<DictionaryEntry | null>(null)
  const [notice, setNotice] = useState("")
  useDocumentTitle(t("dictionary.title"))

  const done = (list: DictionaryEntry[]) => {
    queryClient.setQueryData(query.queryKey, list)
    setEditing(null)
    setNotice(t("dictionary.saved"))
  }
  const save = useMutation({
    mutationFn: ({
      entry,
      term,
      aliases,
    }: {
      entry: DictionaryEntry | null
      term: string
      aliases: string[]
    }) =>
      // A built-in entry is replaced by a company entry under the same term.
      entry?.id != null && !entry.built_in
        ? saveEntry(entry.id, { term, aliases })
        : addEntry({ term, aliases }),
    onSuccess: done,
  })
  const remove = useMutation({
    mutationFn: (entry: DictionaryEntry) => deleteEntry(entry.id ?? 0),
    onSuccess: done,
  })

  const needle = fold(deferred.trim())
  const shown = (entries.data ?? []).filter(
    (entry) =>
      !needle ||
      fold(entry.term).includes(needle) ||
      entry.aliases.some((alias) => fold(alias).includes(needle))
  )

  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.03em]">
          {t("dictionary.title")}
        </h1>
        <p className="text-pretty text-muted-foreground">
          {t("dictionary.description")}
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full max-w-xs">
            <SearchIcon
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-faint-foreground"
            />
            <Input
              type="search"
              name="q"
              autoComplete="off"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("dictionary.search")}
              aria-label={t("dictionary.search")}
              className="pl-8"
            />
          </div>
          {entries.data ? (
            <span className="font-mono text-xs text-faint-foreground tabular-nums">
              {t("dictionary.count", { count: shown.length })}
            </span>
          ) : null}
          {canManageJobs ? (
            <Button
              className="ml-auto"
              onClick={() => setEditing("new")}
              disabled={editing === "new"}
            >
              <PlusIcon data-icon="inline-start" aria-hidden="true" />
              {t("dictionary.add")}
            </Button>
          ) : null}
        </div>
        <p role="status" aria-live="polite" className="sr-only">
          {notice}
        </p>

        {editing === "new" ? (
          <EntryForm
            entry={null}
            pending={save.isPending}
            error={save.isError ? errorMessage(t, save.error) : null}
            onCancel={() => setEditing(null)}
            onSave={(term, aliases) =>
              save.mutate({ entry: null, term, aliases })
            }
          />
        ) : null}

        {entries.isPending ? (
          <div className="flex flex-col gap-2" aria-hidden="true">
            {Array.from({ length: 8 }, (_, row) => (
              <Skeleton key={row} className="h-11 w-full" />
            ))}
          </div>
        ) : entries.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {t("dictionary.loadError")}
          </p>
        ) : shown.length === 0 ? (
          <p className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            {t("dictionary.empty", { query: search.trim() })}
          </p>
        ) : (
          <ul className="flex flex-col divide-y rounded-xl border">
            {shown.map((entry) =>
              typeof editing === "object" &&
              editing !== null &&
              editing.term === entry.term ? (
                <li key={entry.term} className="p-3">
                  <EntryForm
                    entry={entry}
                    pending={save.isPending}
                    error={save.isError ? errorMessage(t, save.error) : null}
                    onCancel={() => setEditing(null)}
                    onSave={(term, aliases) =>
                      save.mutate({ entry, term, aliases })
                    }
                  />
                </li>
              ) : (
                <EntryRow
                  key={entry.term}
                  entry={entry}
                  canManage={canManageJobs}
                  removing={
                    remove.isPending && remove.variables?.term === entry.term
                  }
                  onEdit={() => {
                    save.reset()
                    setEditing({ term: entry.term })
                  }}
                  onRemove={() => setConfirming(entry)}
                />
              )
            )}
          </ul>
        )}
        {remove.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(t, remove.error)}
          </p>
        ) : null}
      </div>

      <AlertDialog
        open={confirming !== null}
        onOpenChange={(open) => {
          if (!open) setConfirming(null)
        }}
      >
        <AlertDialogContent>
          {confirming ? (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {confirming.overrides
                    ? t("dictionary.confirmRestoreTitle", {
                        term: confirming.term,
                      })
                    : t("dictionary.confirmRemoveTitle", {
                        term: confirming.term,
                      })}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {confirming.overrides
                    ? t("dictionary.confirmRestore")
                    : t("dictionary.confirmRemove")}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t("dictionary.cancel")}</AlertDialogCancel>
                <Button
                  variant={confirming.overrides ? "default" : "destructive"}
                  onClick={() => {
                    remove.mutate(confirming)
                    setConfirming(null)
                  }}
                >
                  {confirming.overrides
                    ? t("dictionary.restoreAction")
                    : t("dictionary.removeAction")}
                </Button>
              </AlertDialogFooter>
            </>
          ) : null}
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function EntryRow({
  entry,
  canManage,
  removing,
  onEdit,
  onRemove,
}: {
  entry: DictionaryEntry
  canManage: boolean
  removing: boolean
  onEdit: () => void
  onRemove: () => void
}) {
  const { t } = useTranslation()
  const origin = entry.built_in
    ? t("dictionary.builtIn")
    : entry.overrides
      ? t("dictionary.overrides")
      : t("dictionary.yours")
  return (
    <li className="grid items-center gap-x-4 gap-y-1.5 px-4 py-2.5 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)_auto]">
      <span className="flex min-w-0 items-baseline gap-2">
        <span className="truncate text-sm font-medium">{entry.term}</span>
        <span
          className={cn(
            "shrink-0 text-[11px]",
            entry.built_in ? "text-faint-foreground" : "text-foreground"
          )}
        >
          {origin}
        </span>
      </span>
      <span className="flex min-w-0 flex-wrap gap-1">
        {entry.aliases.length ? (
          entry.aliases.map((alias) => (
            <span
              key={alias}
              className="rounded-md border bg-muted px-1.5 py-px text-xs text-muted-foreground"
            >
              {alias}
            </span>
          ))
        ) : (
          <span className="text-xs text-faint-foreground">
            {t("dictionary.noAliases")}
          </span>
        )}
      </span>
      {canManage ? (
        <span className="flex justify-end gap-1">
          {entry.built_in ? null : (
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={removing}
              aria-label={
                entry.overrides
                  ? t("dictionary.restore", { term: entry.term })
                  : t("dictionary.remove", { term: entry.term })
              }
              onClick={onRemove}
            >
              {entry.overrides ? (
                <RotateCcwIcon aria-hidden="true" />
              ) : (
                <Trash2Icon aria-hidden="true" />
              )}
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("dictionary.edit", { term: entry.term })}
            onClick={onEdit}
          >
            <PencilIcon aria-hidden="true" />
          </Button>
        </span>
      ) : null}
    </li>
  )
}

function EntryForm({
  entry,
  pending,
  error,
  onSave,
  onCancel,
}: {
  entry: DictionaryEntry | null
  pending: boolean
  error: string | null
  onSave: (term: string, aliases: string[]) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const termId = useId()
  const aliasesId = useId()
  const hintId = useId()
  const [term, setTerm] = useState(entry?.term ?? "")
  const [aliases, setAliases] = useState(entry?.aliases.join(", ") ?? "")

  function submit(event: FormEvent) {
    event.preventDefault()
    if (term.trim()) onSave(term.trim(), splitAliases(aliases))
  }

  return (
    <form
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel()
      }}
      className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)]"
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={termId} className="text-sm font-medium">
          {t("dictionary.term")}
        </label>
        <Input
          id={termId}
          name="term"
          autoComplete="off"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          maxLength={80}
          required
          autoFocus
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={aliasesId} className="text-sm font-medium">
          {t("dictionary.aliases")}
        </label>
        <Input
          id={aliasesId}
          name="aliases"
          autoComplete="off"
          value={aliases}
          onChange={(event) => setAliases(event.target.value)}
          aria-describedby={hintId}
        />
        <p id={hintId} className="text-xs text-faint-foreground">
          {t("dictionary.aliasesHint")}
        </p>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive sm:col-span-2">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2 sm:col-span-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("dictionary.cancel")}
        </Button>
        <Button type="submit" disabled={pending || !term.trim()}>
          {t("dictionary.save")}
        </Button>
      </div>
    </form>
  )
}
