import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleAlertIcon, MailIcon, UserMinusIcon, XIcon } from "lucide-react"
import { useId, useState } from "react"
import { useTranslation } from "react-i18next"

import { errorMessage } from "@/api/errors"
import {
  changeRole,
  invitationsQuery,
  invite,
  membersQuery,
  removeMember,
  revokeInvitation,
  type Member,
  type Role,
} from "@/api/team"
import { useRole } from "@/auth/roles"
import { refreshSession, useSession } from "@/auth/session"
import { RoleSelect } from "@/components/role-select"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useApiForm } from "@/hooks/use-api-form"
import { useDocumentTitle } from "@/hooks/use-document-title"

export function TeamPage() {
  const { t } = useTranslation()
  const { session } = useSession()
  const { isAdmin } = useRole()
  useDocumentTitle(t("team.title"))

  if (!session) return null
  const companyId = session.company.id

  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="font-heading text-2xl font-semibold tracking-tight">
          {t("team.title")}
        </h1>
        <p className="text-pretty text-muted-foreground">
          {t("team.description", { company: session.company.name })}
        </p>
        {isAdmin ? null : (
          <p className="text-sm text-muted-foreground">{t("team.readOnly")}</p>
        )}
      </div>
      {isAdmin ? <InviteCard companyId={companyId} /> : null}
      <MembersCard companyId={companyId} />
      {isAdmin ? <PendingInvitationsCard companyId={companyId} /> : null}
    </div>
  )
}

function InviteCard({ companyId }: { companyId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const roleId = useId()
  const [sentTo, setSentTo] = useState<string | null>(null)

  const { formRef, onSubmit, mutation, fieldErrors } = useApiForm(
    (values) => invite(values.email, values.role as Role),
    {
      onSuccess: (_, values) => {
        setSentTo(values.email)
        formRef.current?.reset()
        void queryClient.invalidateQueries({
          queryKey: invitationsQuery(companyId).queryKey,
        })
      },
    }
  )

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>
          <h2>{t("team.invite.title")}</h2>
        </CardTitle>
        <CardDescription>{t("team.invite.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form ref={formRef} onSubmit={onSubmit}>
          <FieldGroup>
            {mutation.isError ? (
              <Alert variant="destructive">
                <CircleAlertIcon aria-hidden="true" />
                <AlertDescription>
                  {errorMessage(t, mutation.error)}
                </AlertDescription>
              </Alert>
            ) : null}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
              <div className="flex-1">
                <TextField
                  name="email"
                  type="email"
                  label={t("team.invite.email")}
                  autoComplete="off"
                  spellCheck={false}
                  required
                  errors={fieldErrors.email}
                />
              </div>
              <Field className="sm:w-auto">
                <FieldLabel htmlFor={roleId}>
                  {t("team.invite.role")}
                </FieldLabel>
                <RoleSelect name="role" id={roleId} />
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-full sm:w-auto">
                <SubmitButton
                  pending={mutation.isPending}
                  label={t("team.invite.submit")}
                  pendingLabel={t("team.invite.submitting")}
                />
              </div>
              <p role="status" className="text-sm text-muted-foreground">
                {sentTo && mutation.isSuccess
                  ? t("team.invite.sent", { email: sentTo })
                  : null}
              </p>
            </div>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function MembersCard({ companyId }: { companyId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { session } = useSession()
  const { isAdmin } = useRole()
  const members = useQuery(membersQuery(companyId))

  async function afterChange(member: Member) {
    await queryClient.invalidateQueries({
      queryKey: membersQuery(companyId).queryKey,
    })
    // My own role changed, or I left: the session must reflect it.
    if (member.user.id === session?.user.id) await refreshSession()
  }

  const roleChange = useMutation({
    mutationFn: ({ member, role }: { member: Member; role: Role }) =>
      changeRole(member.id, role),
    onSuccess: (_, { member }) => afterChange(member),
  })
  const removal = useMutation({
    mutationFn: (member: Member) => removeMember(member.id),
    onSuccess: (_, member) => afterChange(member),
  })
  const failure = roleChange.error ?? removal.error

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>{t("team.members")}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {failure ? (
          <Alert variant="destructive">
            <CircleAlertIcon aria-hidden="true" />
            <AlertDescription>{errorMessage(t, failure)}</AlertDescription>
          </Alert>
        ) : null}
        {members.isPending ? (
          <div className="flex flex-col gap-3" aria-hidden="true">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : null}
        {members.isError ? (
          <Alert variant="destructive">
            <CircleAlertIcon aria-hidden="true" />
            <AlertDescription>
              {errorMessage(t, members.error)}
            </AlertDescription>
          </Alert>
        ) : null}
        {members.data ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("team.member")}</TableHead>
                <TableHead>{t("team.role")}</TableHead>
                {isAdmin ? (
                  <TableHead>
                    <span className="sr-only">{t("team.remove")}</span>
                  </TableHead>
                ) : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.data.map((member) => {
                const isYou = member.user.id === session?.user.id
                return (
                  <TableRow key={member.id}>
                    <TableCell className="max-w-0 min-w-48">
                      <div className="flex min-w-0 flex-col">
                        <span className="flex items-center gap-2 truncate font-medium">
                          <span className="truncate">
                            {member.user.full_name}
                          </span>
                          {isYou ? (
                            <Badge variant="secondary">{t("team.you")}</Badge>
                          ) : null}
                        </span>
                        <span
                          className="truncate text-sm text-muted-foreground"
                          translate="no"
                        >
                          {member.user.email}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {isAdmin ? (
                        <RoleSelect
                          value={member.role}
                          label={t("team.changeRole", {
                            name: member.user.full_name,
                          })}
                          disabled={roleChange.isPending}
                          onChange={(role) =>
                            role !== member.role &&
                            roleChange.mutate({ member, role })
                          }
                        />
                      ) : (
                        t(`roles.${member.role}`)
                      )}
                    </TableCell>
                    {isAdmin ? (
                      <TableCell className="text-right">
                        <RemoveMemberButton
                          member={member}
                          pending={removal.isPending}
                          onConfirm={() => removal.mutate(member)}
                        />
                      </TableCell>
                    ) : null}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        ) : null}
      </CardContent>
    </Card>
  )
}

function RemoveMemberButton({
  member,
  pending,
  onConfirm,
}: {
  member: Member
  pending: boolean
  onConfirm: () => void
}) {
  const { t } = useTranslation()
  const { session } = useSession()
  const name = member.user.full_name

  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("team.removeLabel", { name })}
            disabled={pending}
          />
        }
      >
        <UserMinusIcon data-icon="inline-start" aria-hidden="true" />
        {t("team.remove")}
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t("team.removeTitle", { name, company: session?.company.name })}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t("team.removeDescription")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("team.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>
            {t("team.confirmRemove")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function PendingInvitationsCard({ companyId }: { companyId: string }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const invitations = useQuery(invitationsQuery(companyId))
  const revoke = useMutation({
    mutationFn: revokeInvitation,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: invitationsQuery(companyId).queryKey,
      }),
  })
  const date = new Intl.DateTimeFormat(i18n.resolvedLanguage, {
    dateStyle: "medium",
  })

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>
          <h2>{t("team.pending.title")}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {revoke.isError ? (
          <Alert variant="destructive">
            <CircleAlertIcon aria-hidden="true" />
            <AlertDescription>{errorMessage(t, revoke.error)}</AlertDescription>
          </Alert>
        ) : null}
        {invitations.data && invitations.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("team.pending.empty")}
          </p>
        ) : null}
        {invitations.data && invitations.data.length > 0 ? (
          <ul className="flex flex-col divide-y">
            {invitations.data.map((invitation) => (
              <li
                key={invitation.id}
                className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <MailIcon
                    aria-hidden="true"
                    className="size-4 shrink-0 text-muted-foreground"
                  />
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate font-medium" translate="no">
                      {invitation.email}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {t(`roles.${invitation.role}`)} ·{" "}
                      {t("team.pending.expires", {
                        date: date.format(new Date(invitation.expires_at)),
                      })}
                    </span>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={t("team.pending.revokeLabel", {
                    email: invitation.email,
                  })}
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate(invitation.id)}
                >
                  <XIcon data-icon="inline-start" aria-hidden="true" />
                  {t("team.pending.revoke")}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  )
}
