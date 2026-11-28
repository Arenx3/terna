import {
  BookOpenTextIcon,
  BriefcaseBusinessIcon,
  HouseIcon,
  MailIcon,
  LanguagesIcon,
  LogOutIcon,
  MonitorIcon,
  MoonIcon,
  SunIcon,
  UserPlusIcon,
  UsersIcon,
  ArrowLeftRightIcon,
  PlusIcon,
  ScrollTextIcon,
  WorkflowIcon,
} from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { useSwitchCompany } from "@/components/company-switcher"
import { useTheme } from "@/components/theme-provider"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { useLogout } from "@/components/user-menu"
import { LANGUAGES } from "@/i18n"

/** The item label; the highlighted row wears the marker, like a found line in a résumé. */
function Label({ children }: { children: ReactNode }) {
  return (
    <span className="truncate group-data-selected/command-item:marker">
      {children}
    </span>
  )
}

/**
 * ⌘K: every page and action from the keyboard. Used many times a day, so it
 * opens instantly: no entrance animation.
 */
export function CommandMenu({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { session } = useSession()
  const { isAdmin, canSeeJobs, canManageJobs } = useRole()
  const { setTheme } = useTheme()
  const switchCompany = useSwitchCompany()
  const logout = useLogout()

  function run(action: () => unknown) {
    onOpenChange(false)
    void action()
  }

  const otherCompanies =
    session?.companies.filter((company) => company.id !== session.company.id) ??
    []

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("command.title")}
      description={t("command.description")}
      className="data-open:animate-none data-closed:animate-none"
    >
      <Command>
        <CommandInput placeholder={t("command.placeholder")} />
        <CommandList>
          <CommandEmpty>{t("command.empty")}</CommandEmpty>
          <CommandGroup heading={t("command.pages")}>
            <CommandItem onSelect={() => run(() => navigate("/"))}>
              <HouseIcon aria-hidden="true" />
              <Label>{t("nav.home")}</Label>
            </CommandItem>
            {canSeeJobs ? (
              <CommandItem onSelect={() => run(() => navigate("/jobs"))}>
                <BriefcaseBusinessIcon aria-hidden="true" />
                <Label>{t("nav.jobs")}</Label>
              </CommandItem>
            ) : null}
            <CommandItem onSelect={() => run(() => navigate("/team"))}>
              <UsersIcon aria-hidden="true" />
              <Label>{t("nav.team")}</Label>
            </CommandItem>
            {canManageJobs ? (
              <CommandItem
                onSelect={() => run(() => navigate("/settings/pipeline"))}
              >
                <WorkflowIcon aria-hidden="true" />
                <Label>{t("nav.pipeline")}</Label>
              </CommandItem>
            ) : null}
            {canSeeJobs ? (
              <CommandItem
                onSelect={() => run(() => navigate("/settings/emails"))}
              >
                <MailIcon aria-hidden="true" />
                <Label>{t("nav.emails")}</Label>
              </CommandItem>
            ) : null}
            {canSeeJobs ? (
              <CommandItem
                onSelect={() => run(() => navigate("/settings/synonyms"))}
              >
                <BookOpenTextIcon aria-hidden="true" />
                <Label>{t("nav.dictionary")}</Label>
              </CommandItem>
            ) : null}
            {isAdmin ? (
              <CommandItem
                onSelect={() => run(() => navigate("/settings/audit"))}
              >
                <ScrollTextIcon aria-hidden="true" />
                <Label>{t("nav.audit")}</Label>
              </CommandItem>
            ) : null}
          </CommandGroup>
          {otherCompanies.length > 0 ? (
            <CommandGroup heading={t("command.companies")}>
              {otherCompanies.map((company) => (
                <CommandItem
                  key={company.id}
                  value={`company ${company.name}`}
                  onSelect={() => run(() => switchCompany(company.id))}
                >
                  <ArrowLeftRightIcon aria-hidden="true" />
                  <Label>
                    <span translate="no">{company.name}</span>
                  </Label>
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
          <CommandGroup heading={t("command.actions")}>
            {canManageJobs ? (
              <CommandItem onSelect={() => run(() => navigate("/jobs/new"))}>
                <PlusIcon aria-hidden="true" />
                <Label>{t("command.newJob")}</Label>
              </CommandItem>
            ) : null}
            {isAdmin ? (
              <CommandItem onSelect={() => run(() => navigate("/team#invite"))}>
                <UserPlusIcon aria-hidden="true" />
                <Label>{t("command.invite")}</Label>
              </CommandItem>
            ) : null}
            <CommandItem onSelect={() => run(logout)}>
              <LogOutIcon aria-hidden="true" />
              <Label>{t("command.logout")}</Label>
            </CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading={t("command.preferences")}>
            <CommandItem onSelect={() => run(() => setTheme("dark"))}>
              <MoonIcon aria-hidden="true" />
              <Label>{t("command.themeTo", { name: t("theme.dark") })}</Label>
            </CommandItem>
            <CommandItem onSelect={() => run(() => setTheme("light"))}>
              <SunIcon aria-hidden="true" />
              <Label>{t("command.themeTo", { name: t("theme.light") })}</Label>
            </CommandItem>
            <CommandItem onSelect={() => run(() => setTheme("system"))}>
              <MonitorIcon aria-hidden="true" />
              <Label>{t("command.themeTo", { name: t("theme.system") })}</Label>
            </CommandItem>
            {LANGUAGES.filter(
              (language) => language !== i18n.resolvedLanguage
            ).map((language) => (
              <CommandItem
                key={language}
                onSelect={() => run(() => i18n.changeLanguage(language))}
              >
                <LanguagesIcon aria-hidden="true" />
                <Label>
                  {t("command.languageTo", { name: t(`language.${language}`) })}
                </Label>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
