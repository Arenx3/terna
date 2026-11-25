import { useQueryClient } from "@tanstack/react-query"
import { ChevronsUpDownIcon, LogOutIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { logout } from "@/auth/actions"
import { useSession } from "@/auth/session"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("")
}

export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return async () => {
    await logout()
    queryClient.clear()
    navigate("/login", { replace: true })
  }
}

/** Bottom of the sidebar: who is signed in, and the way out. */
export function UserMenu() {
  const { t } = useTranslation()
  const { session } = useSession()
  const handleLogout = useLogout()

  if (!session) return null
  const { user } = session

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<SidebarMenuButton size="lg" aria-label={t("user.menu")} />}
          >
            <span
              aria-hidden="true"
              className="grid size-8 shrink-0 place-items-center rounded-full bg-secondary text-xs font-semibold"
            >
              {initials(user.full_name)}
            </span>
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="truncate font-medium">{user.full_name}</span>
              <span
                className="truncate text-xs text-muted-foreground"
                translate="no"
              >
                {user.email}
              </span>
            </span>
            <ChevronsUpDownIcon
              aria-hidden="true"
              className="ml-auto text-muted-foreground"
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="min-w-60">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="flex flex-col gap-0.5">
                <span className="text-xs text-muted-foreground">
                  {t("user.signedInAs")}
                </span>
                <span className="truncate text-foreground" translate="no">
                  {user.email}
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
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
