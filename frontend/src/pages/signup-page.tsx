import { CircleAlertIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { errorMessage } from "@/api/errors"
import { signup } from "@/auth/actions"
import { AuthCard } from "@/components/auth-card"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
import { TextLink } from "@/components/text-link"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { FieldGroup } from "@/components/ui/field"
import { useApiForm } from "@/hooks/use-api-form"

export function SignupPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const { formRef, onSubmit, mutation, fieldErrors } = useApiForm(
    (values) =>
      signup({
        company_name: values.company_name,
        full_name: values.full_name,
        email: values.email,
        password: values.password,
      }),
    {
      onSuccess: (_, values) =>
        navigate(
          `/check-email?reason=signup&email=${encodeURIComponent(values.email)}`
        ),
    }
  )

  return (
    <AuthCard
      title={t("auth.signup.title")}
      description={t("auth.signup.description")}
      footer={
        <>
          {t("auth.signup.haveAccount")}{" "}
          <TextLink to="/login">{t("auth.signup.login")}</TextLink>
        </>
      }
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
            name="company_name"
            label={t("auth.signup.companyName")}
            autoComplete="organization"
            maxLength={200}
            required
            errors={fieldErrors.company_name}
          />
          <TextField
            name="full_name"
            label={t("auth.signup.fullName")}
            autoComplete="name"
            maxLength={150}
            required
            errors={fieldErrors.full_name}
          />
          <TextField
            name="email"
            type="email"
            label={t("auth.signup.email")}
            autoComplete="email"
            spellCheck={false}
            required
            errors={fieldErrors.email}
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
            pending={mutation.isPending}
            label={t("auth.signup.submit")}
            pendingLabel={t("auth.signup.submitting")}
          />
        </FieldGroup>
      </form>
    </AuthCard>
  )
}
