import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { Link, Outlet, useParams } from "react-router"

import { careersQuery } from "@/api/careers"
import { BrandMark } from "@/components/brand"
import { LanguageMenu } from "@/components/language-menu"
import { ThemeMenu } from "@/components/theme-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { fillSlots } from "@/lib/slots"

/**
 * A company's public careers pages. The company leads; Terna stays a quiet
 * footnote. Reading width, larger body text: candidates read, they don't operate.
 */
export function CareersLayout() {
  const { t } = useTranslation()
  const { slug = "" } = useParams()
  const careers = useQuery(careersQuery(slug))

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        {t("a11y.skipToContent")}
      </a>
      <header className="border-b">
        <div className="mx-auto flex h-16 w-full max-w-3xl items-center justify-between gap-4 px-6">
          {careers.data ? (
            <Link
              to={`/careers/${slug}`}
              translate="no"
              className="truncate rounded-md font-heading text-[17px] font-semibold tracking-[-0.02em] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {careers.data.company.name}
            </Link>
          ) : careers.isPending ? (
            <Skeleton className="h-5 w-36" />
          ) : (
            <span />
          )}
          <div className="flex items-center gap-1">
            <LanguageMenu />
            <ThemeMenu />
          </div>
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto w-full max-w-3xl flex-1 px-6 py-12 outline-none sm:py-16"
      >
        <Outlet />
      </main>
      <footer className="mx-auto flex w-full max-w-3xl items-center gap-2 px-6 py-8 text-xs text-faint-foreground">
        <BrandMark className="size-3.5" />
        <span>
          {fillSlots(t("careers.poweredBy"), {
            terna: <span translate="no">{t("app.name")}</span>,
          })}
        </span>
      </footer>
    </div>
  )
}
