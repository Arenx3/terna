import { CircleAlertIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { errorMessage } from "@/api/errors"
import { requestPasswordReset } from "@/auth/actions"
import { AuthCard } from "@/components/auth-card"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
import { TextLink } from "@/components/text-link"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { FieldGroup } from "@/components/ui/field"
import { useApiForm } from "@/hooks/use-api-form"

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const { formRef, onSubmit, mutation, fieldErrors } = useApiForm(
    (values) => requestPasswordReset(values.email),
    {
      onSuccess: (_, values) =>
        navigate(
          `/check-email?reason=reset&email=${encodeURIComponent(values.email)}`
        ),
    }
  )

  return (
    <AuthCard
      title={t("auth.forgot.title")}
      description={t("auth.forgot.description")}
      footer={<TextLink to="/login">{t("auth.backToLogin")}</TextLink>}
    >
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
          <TextField
            name="email"
            type="email"
            label={t("auth.email")}
            autoComplete="email"
            spellCheck={false}
            required
            errors={fieldErrors.email}
          />
          <SubmitButton
            pending={mutation.isPending}
            label={t("auth.forgot.submit")}
            pendingLabel={t("auth.forgot.submitting")}
          />
        </FieldGroup>
      </form>
    </AuthCard>
  )
}
