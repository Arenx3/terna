import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import { buttonVariants } from "@/components/ui/button"
import { useDocumentTitle } from "@/hooks/use-document-title"

export function NotFoundPage() {
  const { t } = useTranslation()
  useDocumentTitle(t("notFound.title"))

  return (
    <div className="flex max-w-md flex-col items-start gap-3">
      <h1 className="font-heading text-2xl font-semibold tracking-tight">
        {t("notFound.title")}
      </h1>
      <p className="text-muted-foreground">{t("notFound.description")}</p>
      {/* A real link, styled as a button: it navigates, so it must announce as a link. */}
      <Link to="/" className={buttonVariants({ variant: "outline" })}>
        {t("notFound.back")}
      </Link>
    </div>
  )
}
