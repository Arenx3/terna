import { useQueryClient } from "@tanstack/react-query"
import { ChevronsUpDownIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { switchCompany } from "@/auth/actions"
import { useSession } from "@/auth/session"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

/** The active company; a menu to switch when the person belongs to several. */
export function CompanySwitcher() {
  const { t } = useTranslation()
  const { session } = useSession()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  if (!session) return null
  const { company, companies } = session

  if (companies.length < 2) {
    return (
      <span
        className="max-w-36 truncate text-sm text-muted-foreground sm:max-w-48"
        translate="no"
      >
        {company.name}
      </span>
    )
  }

  async function handleSwitch(companyId: string) {
    if (companyId === company.id) return
    await switchCompany(companyId)
    // Nothing cached from the previous company may survive the switch.
    queryClient.clear()
    navigate("/", { replace: true })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            className="max-w-36 sm:max-w-48"
            aria-label={t("company.switch")}
          />
        }
      >
        <span className="truncate" translate="no">
          {company.name}
        </span>
        <ChevronsUpDownIcon data-icon="inline-end" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-56">
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
  )
}
