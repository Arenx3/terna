import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckIcon, CircleAlertIcon, LockIcon } from "lucide-react"
import { useId, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import { errorMessage } from "@/api/errors"
import {
  renderTemplate,
  resetTemplate,
  saveTemplate,
  TEMPLATE_KINDS,
  templatesQuery,
  unknownVariables,
  type EmailTemplate,
  type TemplateKind,
} from "@/api/messaging"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { relativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

const LANGUAGES = ["es", "en"] as const

function isKind(value: string | null): value is TemplateKind {
  return TEMPLATE_KINDS.some((kind) => kind === value)
}

/** The emails candidates receive, in the company's own words. */
export function EmailsPage() {
  const { t } = useTranslation()
  const { session } = useSession()
  const { isAdmin, canSeeJobs } = useRole()
  const [params, setParams] = useSearchParams()
  const companyId = session?.company.id ?? ""
  const templates = useQuery({
    ...templatesQuery(companyId),
    enabled: canSeeJobs,
  })
  useDocumentTitle(t("emails.title"))

  const raw = params.get("kind")
  const kind: TemplateKind = isKind(raw) ? raw : "application_received"

  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.03em]">
          {t("emails.title")}
        </h1>
        <p className="text-pretty text-muted-foreground">
          {t("emails.description", { company: session?.company.name })}
        </p>
        {isAdmin ? null : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <LockIcon aria-hidden="true" className="size-4" />
            {t("emails.adminOnly")}
          </p>
        )}
      </div>

      {templates.isPending ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : templates.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(t, templates.error)}
        </p>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <nav aria-label={t("emails.title")} className="flex flex-col gap-1">
            {TEMPLATE_KINDS.map((item) => {
              const customized = templates.data.some(
                (row) => row.kind === item && row.customized
              )
              return (
                <button
                  key={item}
                  type="button"
                  aria-current={item === kind ? "page" : undefined}
                  onClick={() => setParams({ kind: item }, { replace: true })}
                  className={cn(
                    "flex flex-col gap-0.5 rounded-lg px-3 py-2.5 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    item === kind ? "bg-muted" : "hover:bg-muted/60"
                  )}
                >
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    {t(`emails.kinds.${item}`)}
                    {customized ? (
                      <span className="text-xs font-normal text-muted-foreground">
                        {t("emails.customized")}
                      </span>
                    ) : null}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {t(`emails.kindHints.${item}`)}
                  </span>
                </button>
              )
            })}
          </nav>

          <Tabs defaultValue="es" className="gap-5">
            <TabsList variant="line" className="w-full justify-start border-b">
              {LANGUAGES.map((language) => (
                <TabsTrigger key={language} value={language}>
                  {t(`language.${language}`)}
                </TabsTrigger>
              ))}
            </TabsList>
            {LANGUAGES.map((language) => {
              const row = templates.data.find(
                (item) => item.kind === kind && item.language === language
              )
              return row ? (
                <TabsContent key={`${kind}-${language}`} value={language}>
                  <TemplateEditor
                    key={`${row.kind}-${row.language}`}
                    template={row}
                    readOnly={!isAdmin}
                  />
                </TabsContent>
              ) : null
            })}
          </Tabs>
        </div>
      )}
    </div>
  )
}

function TemplateEditor({
  template,
  readOnly,
}: {
  template: EmailTemplate
  readOnly: boolean
}) {
  const { t, i18n } = useTranslation()
  const { session } = useSession()
  const queryClient = useQueryClient()
  const subjectId = useId()
  const bodyId = useId()
  const bodyRef = useRef<HTMLTextAreaElement>(null)
  const [subject, setSubject] = useState(template.subject)
  const [body, setBody] = useState(template.body)
  const [saved, setSaved] = useState(false)
  const queryKey = templatesQuery(session?.company.id ?? "").queryKey

  const unknown = unknownVariables(`${subject}\n${body}`, template.variables)
  const dirty = subject !== template.subject || body !== template.body

  const save = useMutation({
    mutationFn: () =>
      saveTemplate(template.kind, template.language, { subject, body }),
    onSuccess: () => {
      setSaved(true)
      void queryClient.invalidateQueries({ queryKey })
    },
  })
  const reset = useMutation({
    mutationFn: () => resetTemplate(template.kind, template.language),
    onSuccess: (restored) => {
      setSubject(restored.subject)
      setBody(restored.body)
      setSaved(false)
      void queryClient.invalidateQueries({ queryKey })
    },
  })

  function insert(variable: string) {
    const field = bodyRef.current
    const token = `{{ ${variable} }}`
    const start = field?.selectionStart ?? body.length
    const end = field?.selectionEnd ?? body.length
    setBody(body.slice(0, start) + token + body.slice(end))
    setSaved(false)
    requestAnimationFrame(() => {
      field?.focus()
      field?.setSelectionRange(start + token.length, start + token.length)
    })
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (!unknown.length) save.mutate()
        }}
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor={subjectId} className="text-sm font-medium">
            {t("emails.subject")}
          </label>
          <Input
            id={subjectId}
            value={subject}
            onChange={(event) => {
              setSubject(event.target.value)
              setSaved(false)
            }}
            maxLength={200}
            disabled={readOnly}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={bodyId} className="text-sm font-medium">
            {t("emails.body")}
          </label>
          <Textarea
            ref={bodyRef}
            id={bodyId}
            value={body}
            onChange={(event) => {
              setBody(event.target.value)
              setSaved(false)
            }}
            rows={14}
            maxLength={5000}
            disabled={readOnly}
            aria-invalid={unknown.length ? true : undefined}
            aria-describedby={
              unknown.length ? `${bodyId}-error` : `${bodyId}-hint`
            }
            className="leading-relaxed"
          />
          {unknown.length ? (
            <p
              id={`${bodyId}-error`}
              role="alert"
              className="flex items-center gap-1.5 text-sm text-destructive"
            >
              <CircleAlertIcon aria-hidden="true" className="size-4" />
              {t("emails.unknownVariable", { names: unknown.join(", ") })}
            </p>
          ) : null}
        </div>
        {readOnly ? null : (
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">
              {t("emails.variables")}
            </legend>
            <p id={`${bodyId}-hint`} className="text-xs text-muted-foreground">
              {t("emails.variablesHint")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {template.variables.map((variable) => (
                <Button
                  key={variable}
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => insert(variable)}
                  className="font-mono"
                >
                  {variable}
                </Button>
              ))}
            </div>
          </fieldset>
        )}
        {readOnly ? null : (
          <div className="flex flex-wrap items-center gap-3 border-t pt-4">
            <Button
              type="submit"
              disabled={!dirty || unknown.length > 0 || save.isPending}
            >
              {save.isPending ? t("emails.saving") : t("emails.save")}
            </Button>
            {template.customized ? (
              <Button
                type="button"
                variant="ghost"
                onClick={() => reset.mutate()}
                disabled={reset.isPending}
              >
                {t("emails.reset")}
              </Button>
            ) : null}
            <span role="status" className="text-[13px] text-muted-foreground">
              {saved && !dirty ? (
                <span className="inline-flex items-center gap-1.5">
                  <CheckIcon
                    aria-hidden="true"
                    className="size-3.5 text-success"
                  />
                  {t("emails.saved")}
                </span>
              ) : null}
            </span>
          </div>
        )}
        {save.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(t, save.error)}
          </p>
        ) : null}
        <p className="text-xs text-faint-foreground">
          {template.customized && template.updated_at
            ? t("emails.updatedBy", {
                name: template.updated_by_name,
                time: relativeTime(template.updated_at, i18n.language),
              })
            : t("emails.default")}
        </p>
      </form>

      <section
        aria-labelledby={`${bodyId}-preview`}
        className="flex flex-col gap-2"
      >
        <h2
          id={`${bodyId}-preview`}
          className="font-sans text-sm font-medium text-muted-foreground"
        >
          {t("emails.preview")}
        </h2>
        <div
          lang={template.language}
          className="flex flex-col gap-3 rounded-xl border bg-card p-5"
        >
          <p className="text-[15px] font-semibold">
            {renderTemplate(subject, template.sample)}
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-line text-foreground/90">
            {renderTemplate(body, template.sample)}
          </p>
        </div>
      </section>
    </div>
  )
}
