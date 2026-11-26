import {
  BriefcaseBusinessIcon,
  HouseIcon,
  MailIcon,
  ScrollTextIcon,
  SearchIcon,
  UsersIcon,
  WorkflowIcon,
  type LucideIcon,
} from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, NavLink, Outlet, useMatch } from "react-router"

import { useRole } from "@/auth/roles"
import { BrandMark } from "@/components/brand"
import { CommandMenu } from "@/components/command-menu"
import { CompanySwitcher } from "@/components/company-switcher"
import { LanguageMenu } from "@/components/language-menu"
import { NotificationsMenu } from "@/components/notifications-menu"
import { ThemeMenu } from "@/components/theme-menu"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { UserMenu } from "@/components/user-menu"
import { cn } from "@/lib/utils"

const IS_MAC =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)
// Key names are the same in every language this app speaks.
const COMMAND_SHORTCUT = IS_MAC ? "⌘K" : "Ctrl K"

/** A navigation entry. Where you are is marked the way evidence is: highlighted. */
function NavItem({
  to,
  end = false,
  icon: Icon,
  label,
}: {
  to: string
  end?: boolean
  icon: LucideIcon
  label: string
}) {
  const active = useMatch({ path: to, end }) !== null
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={active}
        tooltip={label}
        render={<NavLink to={to} end={end} />}
        className="h-9 data-active:bg-transparent data-active:font-medium"
      >
        <Icon aria-hidden="true" />
        <span className={cn(active && "marker")}>{label}</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppShell() {
  const { t } = useTranslation()
  const { canSeeJobs, canManageJobs, isAdmin } = useRole()
  const [commandOpen, setCommandOpen] = useState(false)

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setCommandOpen((open) => !open)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  return (
    <SidebarProvider>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        {t("a11y.skipToContent")}
      </a>
      <Sidebar collapsible="icon" aria-label={t("nav.label")}>
        <SidebarHeader className="gap-3 pt-3">
          <Link
            to="/"
            translate="no"
            className="flex h-8 items-center gap-2 rounded-md px-2 font-heading text-[17px] font-semibold tracking-[-0.02em] group-data-[collapsible=icon]:px-1 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <BrandMark className="size-5" />
            <span className="group-data-[collapsible=icon]:hidden">
              {t("app.name")}
            </span>
          </Link>
          <CompanySwitcher />
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>{t("nav.workspace")}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItem to="/" end icon={HouseIcon} label={t("nav.home")} />
                {canSeeJobs ? (
                  <NavItem
                    to="/jobs"
                    icon={BriefcaseBusinessIcon}
                    label={t("nav.jobs")}
                  />
                ) : null}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          <SidebarGroup>
            <SidebarGroupLabel>{t("nav.company")}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItem to="/team" icon={UsersIcon} label={t("nav.team")} />
                {canManageJobs ? (
                  <NavItem
                    to="/settings/pipeline"
                    icon={WorkflowIcon}
                    label={t("nav.pipeline")}
                  />
                ) : null}
                {canSeeJobs ? (
                  <NavItem
                    to="/settings/emails"
                    icon={MailIcon}
                    label={t("nav.emails")}
                  />
                ) : null}
                {isAdmin ? (
                  <NavItem
                    to="/settings/audit"
                    icon={ScrollTextIcon}
                    label={t("nav.audit")}
                  />
                ) : null}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="pb-3">
          <UserMenu />
        </SidebarFooter>
      </Sidebar>

      <SidebarInset id="main" tabIndex={-1} className="outline-none">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b bg-background px-4">
          <SidebarTrigger className="-ml-1" />
          <Button
            variant="outline"
            className="ml-auto size-9 justify-center gap-2 px-0 text-muted-foreground hover:text-foreground sm:w-full sm:max-w-72 sm:justify-start sm:px-3"
            onClick={() => setCommandOpen(true)}
          >
            <SearchIcon data-icon="inline-start" aria-hidden="true" />
            {/* Icon-only on phones, but the name stays for screen readers. */}
            <span className="sr-only truncate sm:not-sr-only">
              {t("nav.search")}
            </span>
            <Kbd className="ml-auto hidden sm:inline-flex">
              {COMMAND_SHORTCUT}
            </Kbd>
          </Button>
          <div className="flex items-center gap-1">
            <NotificationsMenu />
            <LanguageMenu />
            <ThemeMenu />
          </div>
        </header>
        <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-10 lg:px-10">
          <Outlet />
        </div>
      </SidebarInset>

      <CommandMenu open={commandOpen} onOpenChange={setCommandOpen} />
    </SidebarProvider>
  )
}
