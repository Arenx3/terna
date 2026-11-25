import { useTranslation } from "react-i18next"
import { Outlet } from "react-router"

import { Wordmark } from "@/components/brand"
import { EvidencePanel } from "@/components/evidence-panel"
import { LanguageMenu } from "@/components/language-menu"
import { ThemeMenu } from "@/components/theme-menu"

/** Sign-in, sign-up and email-link screens: the promise on the left, the form on the right. */
export function AuthLayout() {
  const { t } = useTranslation()

  return (
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        {t("a11y.skipToContent")}
      </a>
      <EvidencePanel />
      <div className="flex min-w-0 flex-col">
        <header className="flex h-16 items-center justify-between gap-4 px-6">
          <Wordmark className="lg:invisible" />
          <div className="flex items-center gap-1">
            <LanguageMenu />
            <ThemeMenu />
          </div>
        </header>
        <main
          id="main"
          tabIndex={-1}
          className="flex flex-1 items-start justify-center px-6 pt-[8vh] pb-16 outline-none sm:items-center sm:pt-0"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
