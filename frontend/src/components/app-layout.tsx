import { useTranslation } from "react-i18next"
import { Link, Outlet } from "react-router"

import { LanguageMenu } from "@/components/language-menu"
import { ThemeMenu } from "@/components/theme-menu"

export function AppLayout() {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        {t("a11y.skipToContent")}
      </a>
      <header className="border-b">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4">
          <Link
            to="/"
            translate="no"
            className="rounded-md font-heading text-sm font-medium transition-colors hover:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {t("app.name")}
          </Link>
          <div className="flex items-center gap-1">
            <LanguageMenu />
            <ThemeMenu />
          </div>
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 py-10 outline-none"
      >
        <Outlet />
      </main>
    </div>
  )
}
