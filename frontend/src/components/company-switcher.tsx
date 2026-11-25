import { useQueryClient } from "@tanstack/react-query"
import { ChevronsUpDownIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import type { Role } from "@/api/team"
import { switchCompany } from "@/auth/actions"
import { useSession } from "@/auth/session"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

/** The company's monogram: its first letter on a quiet tile. */
function Monogram({ name }: { name: string }) {
  return (
    <span
      aria-hidden="true"
      className="grid size-8 shrink-0 place-items-center rounded-md border bg-card font-heading text-sm font-semibold"
    >
      {name.trim().charAt(0).toUpperCase()}
    </span>
  )
}

export function useSwitchCompany() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { session } = useSession()

  return async (companyId: string) => {
    if (companyId === session?.company.id) return
    await switchCompany(companyId)
    // Nothing cached from the previous company may survive the switch.
    queryClient.clear()
    navigate("/", { replace: true })
  }
}

/** Top of the sidebar: the active company and your role; a menu to switch when you belong to several. */
export function CompanySwitcher() {
  const { t } = useTranslation()
  const { session } = useSession()
  const handleSwitch = useSwitchCompany()

  if (!session) return null
  const { company, companies } = session

  const identity = (
    <>
      <Monogram name={company.name} />
      <span className="flex min-w-0 flex-col leading-tight">
        <span className="truncate font-medium" translate="no">
          {company.name}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {t(`roles.${company.role as Role}`)}
        </span>
      </span>
    </>
  )

  if (companies.length < 2) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <div className="flex h-12 items-center gap-2 rounded-md p-2 text-sm group-data-[collapsible=icon]:p-0">
            {identity}
          </div>
        </SidebarMenuItem>
      </SidebarMenu>
    )
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger render={<SidebarMenuButton size="lg" />}>
            {identity}
            {/* The visible name stays in the accessible name (WCAG 2.5.3), so
                "click Acme" works for voice control; the purpose follows. */}
            <span className="sr-only">{t("company.switch")}</span>
            <ChevronsUpDownIcon
              aria-hidden="true"
              className="ml-auto text-muted-foreground"
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-60">
            <DropdownMenuGroup>
              <DropdownMenuLabel>{t("company.label")}</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={company.id}
                onValueChange={handleSwitch}
              >
                {companies.map((option) => (
                  <DropdownMenuRadioItem
                    key={option.id}
                    value={option.id}
                    closeOnClick
                    translate="no"
                  >
                    <span className="truncate">{option.name}</span>
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
