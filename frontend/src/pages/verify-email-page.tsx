import { useMutation } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useSearchParams } from "react-router"

import { resendVerification, verifyEmail } from "@/auth/actions"
import { AuthCard } from "@/components/auth-card"
import { SubmitButton } from "@/components/submit-button"
import { TextField } from "@/components/text-field"
import { ButtonLink, TextLink } from "@/components/text-link"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { useApiForm } from "@/hooks/use-api-form"

/** Landing page of the link in the verification email. */
export function VerifyEmailPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get("token") ?? ""
  const started = useRef(false)

  const verification = useMutation({ mutationFn: verifyEmail })
  const { mutate: verify } = verification
  const {
    formRef: resendFormRef,
    onSubmit: onResendSubmit,
    mutation: resendMutation,
    fieldErrors: resendErrors,
  } = useApiForm((values) => resendVerification(values.email), {
    onSuccess: (_, values) =>
      navigate(
        `/check-email?reason=signup&email=${encodeURIComponent(values.email)}`
      ),
  })

  useEffect(() => {
    // Once, even under StrictMode's double effects. Verifying twice is harmless anyway.
    if (started.current) return
    started.current = true
    if (token) verify(token)
  }, [token, verify])

  if (token && (verification.isIdle || verification.isPending)) {
    return (
      <AuthCard title={t("auth.verify.verifying")}>
        <div className="flex justify-center py-4">
          <Spinner
            aria-hidden="true"
            className="size-5 text-muted-foreground"
          />
        </div>
      </AuthCard>
    )
  }

  if (verification.isSuccess) {
    return (
      <AuthCard
        title={t("auth.verify.successTitle")}
        description={t("auth.verify.successDescription")}
      >
        <ButtonLink to="/login">{t("auth.verify.login")}</ButtonLink>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title={t("auth.verify.failedTitle")}
      description={t("auth.verify.failedDescription")}
      footer={<TextLink to="/login">{t("auth.backToLogin")}</TextLink>}
    >
      <form ref={resendFormRef} onSubmit={onResendSubmit}>
        <FieldGroup>
          <TextField
            name="email"
            type="email"
            label={t("auth.email")}
            autoComplete="email"
            spellCheck={false}
            required
            errors={resendErrors.email}
          />
          <SubmitButton
            pending={resendMutation.isPending}
            label={t("auth.verify.resend")}
            pendingLabel={t("auth.forgot.submitting")}
          />
        </FieldGroup>
      </form>
    </AuthCard>
  )
}
