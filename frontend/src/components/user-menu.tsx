import { useQueryClient } from "@tanstack/react-query"
import { LogOutIcon, UserIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { logout } from "@/auth/actions"
import { useSession } from "@/auth/session"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export function UserMenu() {
  const { t } = useTranslation()
  const { session } = useSession()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  if (!session) return null

  async function handleLogout() {
    await logout()
    queryClient.clear()
    navigate("/login", { replace: true })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon" aria-label={t("user.menu")} />
        }
      >
        <UserIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">
              {t("user.signedInAs")}
            </span>
            <span className="truncate text-foreground">
              {session.user.full_name}
            </span>
            <span
              className="truncate text-xs text-muted-foreground"
              translate="no"
            >
              {session.user.email}
            </span>
            <span
              className="truncate text-xs text-muted-foreground"
              translate="no"
            >
              {session.company.name}
            </span>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={handleLogout}>
            <LogOutIcon />
            {t("user.logout")}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
