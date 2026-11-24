import { useMutation } from "@tanstack/react-query"
import { MailIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import { errorMessage } from "@/api/errors"
import { requestPasswordReset, resendVerification } from "@/auth/actions"
import { AuthCard } from "@/components/auth-card"
import { TextLink } from "@/components/text-link"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

/** After sign-up or a reset request: the next step happens in the inbox. */
export function CheckEmailPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const email = params.get("email") ?? ""
  const reason = params.get("reason") === "reset" ? "reset" : "signup"

  const resend = useMutation({
    mutationFn: () =>
      reason === "reset"
        ? requestPasswordReset(email)
        : resendVerification(email),
  })

  return (
    <AuthCard
      title={t("auth.checkEmail.title")}
      description={t(`auth.checkEmail.${reason}`, { email })}
      footer={<TextLink to="/login">{t("auth.backToLogin")}</TextLink>}
    >
      {email ? (
        <div className="flex flex-col items-start gap-3 text-sm text-muted-foreground">
          <p>{t("auth.checkEmail.noEmail")}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => resend.mutate()}
            disabled={resend.isPending || resend.isSuccess}
          >
            {resend.isPending ? (
              <Spinner data-icon="inline-start" aria-hidden="true" />
            ) : (
              <MailIcon data-icon="inline-start" aria-hidden="true" />
            )}
            {t("auth.checkEmail.resend")}
          </Button>
          <p role="status">
            {resend.isSuccess ? t("auth.checkEmail.resent") : null}
            {resend.isError ? errorMessage(t, resend.error) : null}
          </p>
        </div>
      ) : null}
    </AuthCard>
  )
}
