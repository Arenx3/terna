import { useTranslation } from "react-i18next"
import { Link, NavLink, Outlet } from "react-router"

import { useSession } from "@/auth/session"
import { CompanySwitcher } from "@/components/company-switcher"
import { LanguageMenu } from "@/components/language-menu"
import { ThemeMenu } from "@/components/theme-menu"
import { UserMenu } from "@/components/user-menu"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", key: "nav.home", end: true },
  { to: "/team", key: "nav.team", end: false },
] as const

export function AppLayout() {
  const { t } = useTranslation()
  const { status } = useSession()
  const signedIn = status === "authenticated"

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        {t("a11y.skipToContent")}
      </a>
      <header className="border-b">
        <div className="mx-auto flex min-h-14 w-full max-w-5xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 sm:flex-nowrap sm:py-0">
          <div className="flex min-w-0 items-center gap-2">
            <Link
              to="/"
              translate="no"
              className="rounded-md font-heading text-sm font-medium transition-colors hover:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {t("app.name")}
            </Link>
            {signedIn ? (
              <>
                <span aria-hidden="true" className="h-4 w-px bg-border" />
                <CompanySwitcher />
              </>
            ) : null}
          </div>
          {signedIn ? (
            <nav
              aria-label={t("nav.label")}
              className="order-last -ml-2 flex w-full items-center gap-1 sm:order-none sm:ml-0 sm:w-auto"
            >
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-2 py-1 text-sm transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                      isActive ? "text-foreground" : "text-muted-foreground"
                    )
                  }
                >
                  {t(item.key)}
                </NavLink>
              ))}
            </nav>
          ) : null}
          <div className="ml-auto flex items-center gap-1">
            <LanguageMenu />
            <ThemeMenu />
            <UserMenu />
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
