import { CircleAlertIcon, SearchXIcon } from "lucide-react"
import { useTranslation } from "react-i18next"

/** A careers page that doesn't exist (or closed), or one that failed to load. */
export function CareersNotice({ notFound }: { notFound: boolean }) {
  const { t } = useTranslation()
  const Icon = notFound ? SearchXIcon : CircleAlertIcon
  return (
    <div className="flex flex-col items-start gap-4 py-10">
      <Icon aria-hidden="true" className="size-6 text-faint-foreground" />
      <h1 className="text-2xl font-semibold tracking-[-0.02em]">
        {notFound ? t("careers.notFound.title") : t("careers.loadError")}
      </h1>
      {notFound ? (
        <p className="text-muted-foreground">
          {t("careers.notFound.description")}
        </p>
      ) : null}
    </div>
  )
}
