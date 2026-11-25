import { useQuery } from "@tanstack/react-query"
import {
  CircleAlertIcon,
  CircleCheckIcon,
  FileTextIcon,
  UploadIcon,
  XIcon,
} from "lucide-react"
import { useEffect, useId, useRef, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import {
  applyFormQuery,
  requestUpload,
  submitApplication,
  uploadFile,
  UploadFailedError,
} from "@/api/careers"
import type { Schemas } from "@/api/client"
import { ApiError, errorMessage } from "@/api/errors"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { fillSlots } from "@/lib/slots"
import { cn } from "@/lib/utils"

type ResumeContentType = Schemas["UploadRequestRequest"]["content_type"]

const TYPES_BY_EXTENSION: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

/** The résumé's content type, from its extension when the browser doesn't know it. */
function contentTypeOf(file: File) {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? ""
  return TYPES_BY_EXTENSION[extension] ?? file.type
}

function fileSize(bytes: number, language: string) {
  const megabytes = bytes / (1024 * 1024)
  return new Intl.NumberFormat(language, {
    style: "unit",
    unit: megabytes >= 1 ? "megabyte" : "kilobyte",
    maximumFractionDigits: 1,
  }).format(megabytes >= 1 ? megabytes : bytes / 1024)
}

type Problems = Partial<
  Record<"full_name" | "email" | "resume" | "consent", string>
>

/**
 * Applying without an account: details, a résumé straight to storage, and
 * consent before any of it is kept.
 */
export function ApplyForm({
  slug,
  jobId,
  jobTitle,
}: {
  slug: string
  jobId: string
  jobTitle: string
}) {
  const { t, i18n } = useTranslation()
  const form = useQuery(applyFormQuery(slug, jobId))
  const ids = {
    name: useId(),
    email: useId(),
    phone: useId(),
    file: useId(),
    consent: useId(),
  }
  const doneRef = useRef<HTMLHeadingElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [consent, setConsent] = useState(false)
  const [problems, setProblems] = useState<Problems>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ name: string; email: string } | null>(null)

  useEffect(() => {
    if (done) doneRef.current?.focus()
  }, [done])

  function pick(next: File | null) {
    setFile(next)
    setProblems((current) => ({ ...current, resume: undefined }))
    if (!next || !form.data) return
    if (!form.data.content_types.includes(contentTypeOf(next))) {
      setProblems((current) => ({
        ...current,
        resume: t("careers.apply.wrongType"),
      }))
    } else if (next.size > form.data.max_size) {
      setProblems((current) => ({
        ...current,
        resume: t("careers.apply.tooLarge"),
      }))
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.data || busy) return
    const values = new FormData(event.currentTarget)
    const fullName = String(values.get("full_name") ?? "").trim()
    const email = String(values.get("email") ?? "").trim()
    const found: Problems = {
      full_name: fullName ? undefined : t("careers.apply.required"),
      email: email ? undefined : t("careers.apply.required"),
      resume: !file ? t("careers.apply.resumeRequired") : problems.resume,
      consent: consent ? undefined : t("careers.apply.consentRequired"),
    }
    setProblems(found)
    setFailure(null)
    const first = Object.entries(found).find(([, message]) => message)?.[0]
    if (first || !file) {
      const target = {
        full_name: ids.name,
        email: ids.email,
        resume: ids.file,
        consent: ids.consent,
      }
      document.getElementById(target[first as keyof typeof target])?.focus()
      return
    }

    setBusy(true)
    try {
      const contentType = contentTypeOf(file)
      const ticket = await requestUpload(slug, jobId, {
        form_token: form.data.form_token,
        consent: true,
        filename: file.name,
        content_type: contentType as ResumeContentType,
        size: file.size,
      })
      setProgress(0)
      await uploadFile(ticket.url, ticket.headers, file, setProgress)
      setProgress(null)
      await submitApplication(slug, jobId, {
        form_token: form.data.form_token,
        upload: ticket.ticket,
        consent: true,
        notice_version: form.data.privacy_notice_version,
        full_name: fullName,
        email,
        phone: String(values.get("phone") ?? "").trim(),
        website: String(values.get("website") ?? ""),
      })
      setDone({ name: fullName.split(" ")[0] ?? fullName, email })
    } catch (error) {
      setProgress(null)
      if (error instanceof UploadFailedError) {
        setFailure(t("careers.apply.uploadFailed"))
      } else if (error instanceof ApiError && error.fields.email) {
        setProblems((current) => ({
          ...current,
          email: error.fields.email?.[0],
        }))
        document.getElementById(ids.email)?.focus()
      } else {
        setFailure(errorMessage(t, error))
      }
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border bg-card p-6">
        <CircleCheckIcon aria-hidden="true" className="size-6 text-success" />
        <h2
          ref={doneRef}
          tabIndex={-1}
          className="text-xl font-semibold tracking-[-0.02em] outline-none"
        >
          {t("careers.apply.doneTitle", { name: done.name })}
        </h2>
        <p className="text-base text-muted-foreground">
          {t("careers.apply.doneBody", { job: jobTitle, email: done.email })}
        </p>
      </div>
    )
  }

  if (form.isPending) return <Skeleton className="h-96 w-full rounded-xl" />
  if (form.isError) return null // the job closed meanwhile; the page says so on reload

  const errorFor = (name: keyof Problems) =>
    problems[name] ? [{ message: problems[name] }] : []

  return (
    <form
      noValidate
      onSubmit={(event) => void onSubmit(event)}
      className="flex flex-col gap-5"
      aria-describedby={failure ? `${ids.file}-failure` : undefined}
    >
      {failure ? (
        <Alert variant="destructive" id={`${ids.file}-failure`}>
          <CircleAlertIcon aria-hidden="true" />
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      ) : null}

      <Field data-invalid={problems.full_name ? true : undefined}>
        <FieldLabel htmlFor={ids.name}>
          {t("careers.apply.fullName")}
        </FieldLabel>
        <Input
          id={ids.name}
          name="full_name"
          autoComplete="name"
          maxLength={150}
          aria-invalid={problems.full_name ? true : undefined}
          aria-describedby={
            problems.full_name ? `${ids.name}-error` : undefined
          }
        />
        <FieldError id={`${ids.name}-error`} errors={errorFor("full_name")} />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field data-invalid={problems.email ? true : undefined}>
          <FieldLabel htmlFor={ids.email}>
            {t("careers.apply.email")}
          </FieldLabel>
          <Input
            id={ids.email}
            name="email"
            type="email"
            autoComplete="email"
            spellCheck={false}
            aria-invalid={problems.email ? true : undefined}
            aria-describedby={problems.email ? `${ids.email}-error` : undefined}
          />
          <FieldError id={`${ids.email}-error`} errors={errorFor("email")} />
        </Field>
        <Field>
          <FieldLabel htmlFor={ids.phone}>
            {t("careers.apply.phone")}{" "}
            <span className="font-normal text-faint-foreground">
              {t("careers.apply.optional")}
            </span>
          </FieldLabel>
          <Input
            id={ids.phone}
            name="phone"
            type="tel"
            autoComplete="tel"
            maxLength={40}
          />
        </Field>
      </div>

      <Field data-invalid={problems.resume ? true : undefined}>
        <span className="text-sm font-medium">{t("careers.apply.resume")}</span>
        {file ? (
          <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3">
            <FileTextIcon
              aria-hidden="true"
              className="size-5 shrink-0 text-muted-foreground"
            />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-medium">{file.name}</span>
              <span className="text-xs text-muted-foreground">
                {fileSize(file.size, i18n.language)}
              </span>
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => pick(null)}
              disabled={busy}
              aria-label={t("careers.apply.remove", { name: file.name })}
            >
              <XIcon aria-hidden="true" />
            </Button>
          </div>
        ) : (
          <label
            htmlFor={ids.file}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              pick(event.dataTransfer.files[0] ?? null)
            }}
            className={cn(
              "flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed px-6 py-8 text-center transition-colors has-focus-visible:ring-2 has-focus-visible:ring-ring",
              dragging ? "border-primary-edge bg-muted" : "hover:bg-muted/60"
            )}
          >
            <UploadIcon
              aria-hidden="true"
              className="size-5 text-muted-foreground"
            />
            <span className="text-sm">
              {fillSlots(t("careers.apply.drop"), {
                choose: (
                  <span className="font-medium underline underline-offset-4">
                    {t("careers.apply.choose")}
                  </span>
                ),
              })}
            </span>
            <span className="text-xs text-muted-foreground">
              {t("careers.apply.formats")}
            </span>
            <input
              id={ids.file}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="sr-only"
              aria-invalid={problems.resume ? true : undefined}
              aria-describedby={`${ids.file}-hint${problems.resume ? ` ${ids.file}-error` : ""}`}
              onChange={(event) => pick(event.target.files?.[0] ?? null)}
            />
            <span id={`${ids.file}-hint`} className="sr-only">
              {t("careers.apply.formats")}
            </span>
          </label>
        )}
        <FieldError id={`${ids.file}-error`} errors={errorFor("resume")} />
      </Field>

      {/* Left empty by people; bots that fill every field give themselves away. */}
      <div
        aria-hidden="true"
        className="absolute -left-[9999px] h-px w-px overflow-hidden"
      >
        <label>
          {t("careers.apply.honeypot")}
          <input name="website" type="text" tabIndex={-1} autoComplete="off" />
        </label>
      </div>

      <Field data-invalid={problems.consent ? true : undefined}>
        <div className="flex items-start gap-3">
          <input
            id={ids.consent}
            type="checkbox"
            checked={consent}
            onChange={(event) => {
              setConsent(event.target.checked)
              setProblems((current) => ({ ...current, consent: undefined }))
            }}
            aria-invalid={problems.consent ? true : undefined}
            aria-describedby={
              problems.consent ? `${ids.consent}-error` : undefined
            }
            className="mt-0.5 size-4 shrink-0 accent-[var(--primary-edge)]"
          />
          <label htmlFor={ids.consent} className="text-sm leading-snug">
            {fillSlots(t("careers.apply.consent"), {
              notice: (
                <Link
                  to={`/careers/${slug}/privacy`}
                  target="_blank"
                  className="font-medium underline underline-offset-4"
                >
                  {t("careers.apply.notice")}
                </Link>
              ),
            })}
          </label>
        </div>
        <FieldError id={`${ids.consent}-error`} errors={errorFor("consent")} />
      </Field>

      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" size="lg" disabled={busy} className="px-4">
          {busy && progress === null
            ? t("careers.apply.sending")
            : t("careers.apply.submit")}
        </Button>
        <span role="status" className="text-sm text-muted-foreground">
          {progress !== null
            ? t("careers.apply.uploading", { percent: progress })
            : ""}
        </span>
      </div>
    </form>
  )
}
