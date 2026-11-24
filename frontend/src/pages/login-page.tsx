import { useMutation } from "@tanstack/react-query"
import { CircleAlertIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate, useSearchParams } from "react-router"

import { ApiError, errorMessage } from "@/api/errors"
import { login, resendVerification } from "@/auth/actions"
import { AuthCard } from "@/components/auth-card"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
import { safeNext, TextLink } from "@/components/text-link"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { useApiForm } from "@/hooks/use-api-form"

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get("next"))

  const { formRef, onSubmit, mutation, fieldErrors } = useApiForm(
    (values) => login(values.email, values.password),
    { onSuccess: () => navigate(next, { replace: true }) }
  )
  const resend = useMutation({ mutationFn: resendVerification })
  const unverified =
    mutation.error instanceof ApiError &&
    mutation.error.code === "email_not_verified"

  function resendLink() {
    const email = formRef.current
      ? new FormData(formRef.current).get("email")
      : null
    if (email) resend.mutate(String(email))
  }

  return (
    <AuthCard
      title={t("auth.login.title")}
      description={t("auth.login.description")}
      footer={
        <>
          {t("auth.login.noAccount")}{" "}
          <TextLink to="/signup">{t("auth.login.createAccount")}</TextLink>
        </>
      }
    >
      <form ref={formRef} onSubmit={onSubmit}>
        <FieldGroup>
          {mutation.isError ? (
            <Alert variant="destructive">
              <CircleAlertIcon aria-hidden="true" />
              <AlertDescription>
                <p>{errorMessage(t, mutation.error)}</p>
                {unverified && !resend.isSuccess ? (
                  <Button
                    type="button"
                    variant="link"
                    className="h-auto p-0"
                    onClick={resendLink}
                    disabled={resend.isPending}
                  >
                    {t("auth.login.resend")}
                  </Button>
                ) : null}
                {resend.isSuccess ? (
                  <p role="status">{t("auth.login.resent")}</p>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}
          <TextField
            name="email"
            type="email"
            label={t("auth.email")}
            autoComplete="email"
            spellCheck={false}
            required
            errors={fieldErrors.email}
          />
          <TextField
            name="password"
            type="password"
            label={t("auth.password")}
            autoComplete="current-password"
            required
            errors={fieldErrors.password}
          />
          <TextLink
            to="/forgot-password"
            className="self-start text-sm font-normal"
          >
            {t("auth.login.forgot")}
          </TextLink>
          <SubmitButton
            pending={mutation.isPending}
            label={t("auth.login.submit")}
            pendingLabel={t("auth.login.submitting")}
          />
        </FieldGroup>
      </form>
    </AuthCard>
  )
}
