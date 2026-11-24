import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleAlertIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate, useSearchParams } from "react-router"

import { ApiError, errorMessage } from "@/api/errors"
import { acceptInvitation, logout, previewInvitation } from "@/auth/actions"
import { useSession } from "@/auth/session"
import { AuthCard } from "@/components/auth-card"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
import { ButtonLink, TextLink } from "@/components/text-link"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { useApiForm } from "@/hooks/use-api-form"

/** Landing page of the link in the invitation email. */
export function AcceptInvitationPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const token = params.get("token") ?? ""
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { session } = useSession()

  const preview = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => previewInvitation(token),
    enabled: token !== "",
    retry: false,
  })

  function joined() {
    queryClient.clear()
    navigate("/", { replace: true })
  }

  const join = useMutation({
    mutationFn: () => acceptInvitation(token),
    onSuccess: joined,
  })
  const {
    formRef,
    onSubmit,
    mutation: signup,
    fieldErrors,
  } = useApiForm(
    (values) =>
      acceptInvitation(token, {
        full_name: values.full_name,
        password: values.password,
      }),
    { onSuccess: joined }
  )

  if (token && preview.isPending) {
    return (
      <AuthCard title={t("invitation.checking")}>
        <div className="flex justify-center py-4">
          <Spinner
            aria-hidden="true"
            className="size-5 text-muted-foreground"
          />
        </div>
      </AuthCard>
    )
  }

  const invitation = preview.data
  const status =
    !token || preview.isError ? "invalid" : (invitation?.status ?? "invalid")

  if (!invitation || status !== "valid") {
    const reason =
      status === "expired" || status === "used" || status === "revoked"
        ? status
        : "invalid"
    return (
      <AuthCard
        title={t("invitation.invalidTitle")}
        description={t(`invitation.${reason}`)}
        footer={<TextLink to="/login">{t("auth.backToLogin")}</TextLink>}
      />
    )
  }

  const vars = {
    company: invitation.company_name,
    role: t(`roles.${invitation.role}`),
    email: invitation.email,
  }
  const failure = join.error ?? signup.error
  const failureAlert = failure ? (
    <Alert variant="destructive">
      <CircleAlertIcon aria-hidden="true" />
      <AlertDescription>{errorMessage(t, failure)}</AlertDescription>
    </Alert>
  ) : null

  // Signed in as the invited address: one click.
  if (session && session.user.email === invitation.email) {
    return (
      <AuthCard
        title={t("invitation.title", vars)}
        description={t("invitation.description", vars)}
      >
        <div className="flex flex-col gap-4">
          {failureAlert}
          <Button
            className="w-full"
            onClick={() => join.mutate()}
            disabled={join.isPending}
          >
            {join.isPending ? (
              <Spinner data-icon="inline-start" aria-hidden="true" />
            ) : null}
            {t("invitation.join", vars)}
          </Button>
        </div>
      </AuthCard>
    )
  }

  // Signed in as someone else.
  if (session) {
    return (
      <AuthCard
        title={t("invitation.title", vars)}
        description={t("invitation.wrongAccount", {
          email: invitation.email,
          current: session.user.email,
        })}
      >
        <Button
          variant="outline"
          className="w-full"
          onClick={async () => {
            await logout()
            queryClient.clear()
          }}
        >
          {t("invitation.switchAccount")}
        </Button>
      </AuthCard>
    )
  }

  // Has an account, not signed in: log in, then come back here.
  if (invitation.account_exists) {
    const next = `/invitations/accept?token=${encodeURIComponent(token)}`
    return (
      <AuthCard
        title={t("invitation.title", vars)}
        description={t("invitation.loginToAccept", vars)}
      >
        <ButtonLink to={`/login?next=${encodeURIComponent(next)}`}>
          {t("invitation.login")}
        </ButtonLink>
      </AuthCard>
    )
  }

  // New to Terna: create the account and join in one step.
  const invalidLink =
    signup.error instanceof ApiError &&
    signup.error.code?.startsWith("invitation_")

  return (
    <AuthCard
      title={t("invitation.title", vars)}
      description={`${t("invitation.description", vars)} ${t("invitation.createAccount")}`}
    >
      <form ref={formRef} onSubmit={onSubmit}>
        <FieldGroup>
          {failureAlert}
          <TextField
            name="full_name"
            label={t("invitation.fullName")}
            autoComplete="name"
            maxLength={150}
            required
            errors={fieldErrors.full_name}
          />
          <TextField
            name="password"
            type="password"
            label={t("auth.password")}
            description={t("auth.signup.passwordHint")}
            autoComplete="new-password"
            minLength={10}
            required
            errors={fieldErrors.password}
          />
          <SubmitButton
            pending={signup.isPending}
            label={t("invitation.submit")}
            pendingLabel={t("invitation.submitting")}
          />
          {invalidLink ? (
            <TextLink to="/login" className="self-center text-sm">
              {t("auth.backToLogin")}
            </TextLink>
          ) : null}
        </FieldGroup>
      </form>
    </AuthCard>
  )
}
