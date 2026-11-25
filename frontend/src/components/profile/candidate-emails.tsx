import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MailPlusIcon } from "lucide-react"
import { useId, useState } from "react"
import { useTranslation } from "react-i18next"

import { errorMessage } from "@/api/errors"
import {
  cancelEmail,
  candidateEmailsQuery,
  emailDraft,
  nineAmIn,
  retryEmail,
  sendEmail,
  TEMPLATE_KINDS,
  type CandidateEmail,
  type TemplateKind,
} from "@/api/messaging"
import type { Profile } from "@/api/profile"
import { useSession } from "@/auth/session"
import { ChoiceSelect } from "@/components/choice-select"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { relativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

export type When = "now" | "tomorrow" | "inThreeDays"

export function scheduledFor(when: When) {
  return when === "now" ? null : nineAmIn(when === "tomorrow" ? 1 : 3)
}

/** Every email this candidate was sent, or will be, and a way to write one. */
export function CandidateEmails({ profile }: { profile: Profile }) {
  const { t } = useTranslation()
  const { session } = useSession()
  const queryClient = useQueryClient()
  const companyId = session?.company.id ?? ""
  const emails = useQuery(candidateEmailsQuery(companyId, profile.id))
  const [composing, setComposing] = useState(false)
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: ["applications", companyId, profile.id],
    })

  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "retry" | "cancel" }) =>
      action === "retry" ? retryEmail(id) : cancelEmail(id),
    onSuccess: refresh,
  })

  return (
    <div className="flex flex-col gap-4">
      {profile.can_manage ? (
        <Button
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => setComposing(true)}
        >
          <MailPlusIcon data-icon="inline-start" aria-hidden="true" />
          {t("emails.write")}
        </Button>
      ) : null}
      {emails.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : (emails.data ?? []).length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("emails.none")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {emails.data?.map((email) => (
            <EmailRow
              key={email.id}
              email={email}
              canManage={profile.can_manage}
              busy={act.isPending}
              onRetry={() => act.mutate({ id: email.id, action: "retry" })}
              onCancel={() => act.mutate({ id: email.id, action: "cancel" })}
            />
          ))}
        </ul>
      )}
      {composing ? (
        <ComposeDialog
          profile={profile}
          onClose={() => setComposing(false)}
          onSent={() => {
            setComposing(false)
            void refresh()
          }}
        />
      ) : null}
    </div>
  )
}

const STATUS_DOT: Record<CandidateEmail["status"], string> = {
  queued: "border border-dashed border-faint-foreground",
  sent: "bg-success",
  failed: "bg-destructive",
  canceled: "bg-faint-foreground/60",
}

function EmailRow({
  email,
  canManage,
  busy,
  onRetry,
  onCancel,
}: {
  email: CandidateEmail
  canManage: boolean
  busy: boolean
  onRetry: () => void
  onCancel: () => void
}) {
  const { t, i18n } = useTranslation()
  const when =
    email.status === "sent" && email.sent_at
      ? t("emails.sentAt", { time: relativeTime(email.sent_at, i18n.language) })
      : email.status === "queued" && email.scheduled_for
        ? t("emails.goesOut", {
            time: relativeTime(email.scheduled_for, i18n.language),
          })
        : relativeTime(email.created_at, i18n.language)

  return (
    <li className="rounded-lg border bg-card">
      <details className="group">
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 focus-visible:rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          <span className="min-w-0 flex-1 truncate text-sm font-medium">
            {email.subject}
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              aria-hidden="true"
              className={cn("size-2 rounded-full", STATUS_DOT[email.status])}
            />
            {t(`emails.status.${email.status}`)}
          </span>
          <span className="w-full text-xs text-faint-foreground">
            {t(`emails.kinds.${email.kind}`)}
            {" · "}
            {when}
            {" · "}
            {email.created_by_name
              ? t("emails.createdBy", { name: email.created_by_name })
              : t("emails.automatic")}
          </span>
        </summary>
        <div className="flex flex-col gap-3 border-t px-4 py-3">
          <p
            lang={email.language}
            className="text-sm leading-relaxed whitespace-pre-line text-foreground/90"
          >
            {email.body}
          </p>
          {email.status === "failed" ? (
            <p className="text-xs text-destructive">{email.failure_reason}</p>
          ) : null}
          {canManage && email.status === "failed" ? (
            <Button
              size="sm"
              variant="outline"
              className="self-start"
              disabled={busy}
              onClick={onRetry}
            >
              {t("emails.retry")}
            </Button>
          ) : null}
          {canManage && email.status === "queued" && email.scheduled_for ? (
            <Button
              size="sm"
              variant="ghost"
              className="self-start"
              disabled={busy}
              onClick={onCancel}
            >
              {t("emails.cancel")}
            </Button>
          ) : null}
        </div>
      </details>
    </li>
  )
}

function ComposeDialog({
  profile,
  onClose,
  onSent,
}: {
  profile: Profile
  onClose: () => void
  onSent: () => void
}) {
  const { t } = useTranslation()
  const ids = { kind: useId(), subject: useId(), body: useId(), when: useId() }
  const [kind, setKind] = useState<TemplateKind>("interview_invitation")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [when, setWhen] = useState<When>("now")

  const draft = useQuery({
    queryKey: ["email-draft", profile.id, kind],
    queryFn: () => emailDraft(profile.id, kind),
    staleTime: 0,
    gcTime: 0,
  })
  // A new template was picked: start from its text (adjusting state while rendering).
  const [loadedFor, setLoadedFor] = useState<TemplateKind | null>(null)
  if (draft.data && draft.data.kind !== loadedFor) {
    setLoadedFor(draft.data.kind)
    setSubject(draft.data.subject)
    setBody(draft.data.body)
  }

  const send = useMutation({
    mutationFn: () =>
      sendEmail(profile.id, {
        kind,
        subject,
        body,
        scheduled_for: scheduledFor(when),
      }),
    onSuccess: onSent,
  })

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-xl">
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            send.mutate()
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {t("emails.composeTitle", { name: profile.candidate.full_name })}
            </DialogTitle>
            <DialogDescription>{profile.candidate.email}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label htmlFor={ids.kind} className="text-sm font-medium">
                {t("emails.template")}
              </label>
              <ChoiceSelect
                id={ids.kind}
                value={kind}
                onChange={setKind}
                choices={TEMPLATE_KINDS.map((value) => ({
                  value,
                  label: t(`emails.kinds.${value}`),
                }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={ids.when} className="text-sm font-medium">
                {t("emails.when")}
              </label>
              <ChoiceSelect
                id={ids.when}
                value={when}
                onChange={setWhen}
                choices={(["now", "tomorrow", "inThreeDays"] as const).map(
                  (value) => ({
                    value,
                    label: t(`emails.${value}`),
                  })
                )}
              />
            </div>
          </div>
          {draft.isPending ? (
            <p role="status" className="text-sm text-muted-foreground">
              {t("emails.loadingDraft")}
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <label htmlFor={ids.subject} className="text-sm font-medium">
                  {t("emails.subject")}
                </label>
                <Input
                  id={ids.subject}
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  maxLength={200}
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor={ids.body} className="text-sm font-medium">
                  {t("emails.body")}
                </label>
                <Textarea
                  id={ids.body}
                  lang={draft.data?.language}
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  rows={10}
                  maxLength={5000}
                  required
                  className="leading-relaxed"
                />
              </div>
            </>
          )}
          {send.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(t, send.error) || t("emails.sendFailed")}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              {t("board.reject.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={
                send.isPending ||
                draft.isPending ||
                !subject.trim() ||
                !body.trim()
              }
            >
              {when === "now" ? t("emails.send") : t("emails.schedule")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
