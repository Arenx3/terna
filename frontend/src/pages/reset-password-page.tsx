import { CircleAlertIcon } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import { ApiError, errorMessage } from "@/api/errors"
import { confirmPasswordReset } from "@/auth/actions"
import { AuthCard } from "@/components/auth-card"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
import { ButtonLink } from "@/components/text-link"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { FieldGroup } from "@/components/ui/field"
import { useApiForm } from "@/hooks/use-api-form"

/** Landing page of the link in the password reset email. */
export function ResetPasswordPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const uid = params.get("uid") ?? ""
  const token = params.get("token") ?? ""
  const [mismatch, setMismatch] = useState(false)

  const { formRef, onSubmit, mutation, fieldErrors } = useApiForm((values) =>
    confirmPasswordReset({ uid, token, password: values.password })
  )

  const linkBroken =
    !uid ||
    !token ||
    (mutation.error instanceof ApiError &&
      mutation.error.code === "invalid_link")

  if (linkBroken) {
    return (
      <AuthCard
        title={t("auth.reset.invalidTitle")}
        description={t("auth.reset.invalidDescription")}
      >
        <ButtonLink to="/forgot-password">
          {t("auth.reset.requestNew")}
        </ButtonLink>
      </AuthCard>
    )
  }

  if (mutation.isSuccess) {
    return (
      <AuthCard
        title={t("auth.reset.successTitle")}
        description={t("auth.reset.successDescription")}
      >
        <ButtonLink to="/login">{t("auth.reset.login")}</ButtonLink>
      </AuthCard>
    )
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    const data = new FormData(event.currentTarget)
    const differs = data.get("password") !== data.get("confirm")
    setMismatch(differs)
    if (differs) {
      event.preventDefault()
      return
    }
    onSubmit(event)
  }

  return (
    <AuthCard title={t("auth.reset.title")}>
      <form ref={formRef} onSubmit={handleSubmit}>
        <FieldGroup>
          {mutation.isError ? (
            <Alert variant="destructive">
              <CircleAlertIcon aria-hidden="true" />
              <AlertDescription>
                {errorMessage(t, mutation.error)}
              </AlertDescription>
            </Alert>
          ) : null}
          <TextField
            name="password"
            type="password"
            label={t("auth.reset.password")}
            description={t("auth.signup.passwordHint")}
            autoComplete="new-password"
            minLength={10}
            required
            errors={fieldErrors.password}
          />
          <TextField
            name="confirm"
            type="password"
            label={t("auth.reset.confirm")}
            autoComplete="new-password"
            required
            errors={mismatch ? [t("auth.reset.mismatch")] : []}
          />
          <SubmitButton
            pending={mutation.isPending}
            label={t("auth.reset.submit")}
            pendingLabel={t("auth.reset.submitting")}
          />
        </FieldGroup>
      </form>
    </AuthCard>
  )
}
