import { useEffect } from "react"
import { useTranslation } from "react-i18next"

/** Sets the tab title as "<page> · Terna", following the current language. */
export function useDocumentTitle(page?: string) {
  const { t } = useTranslation()
  const app = t("app.name")

  useEffect(() => {
    document.title = page ? `${page} · ${app}` : app
  }, [page, app])
}
