import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BellIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { inboxQuery, markRead, type AppNotification } from "@/api/profile"
import { useRole } from "@/auth/roles"
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
import { relativeTime } from "@/lib/format"
import { fillSlots } from "@/lib/slots"
import { cn } from "@/lib/utils"

/** Mentions and assignments, in the active company. Checked every half minute. */
export function NotificationsMenu() {
  const { t, i18n } = useTranslation()
  const { session } = useSession()
  const { canSeeJobs } = useRole()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const companyId = session?.company.id ?? ""
  const inbox = useQuery(inboxQuery(companyId))
  const unread = inbox.data?.unread ?? 0

  const read = useMutation({
    mutationFn: (ids: number[]) => markRead(ids),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications", companyId] }),
  })

  // Boards are for people who work on jobs; interviewers open the candidate alone.
  const href = (item: AppNotification) =>
    canSeeJobs
      ? `/jobs/${item.job_id}/candidates/${item.application}`
      : `/applications/${item.application}`

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            aria-label={
              unread
                ? `${t("notifications.label")}: ${t("notifications.unread", { count: unread })}`
                : t("notifications.label")
            }
            className="relative"
          />
        }
      >
        <BellIcon aria-hidden="true" />
        {unread ? (
          <span
            aria-hidden="true"
            className="absolute top-1 right-1 grid h-4 min-w-4 place-items-center rounded-full bg-primary px-1 font-mono text-[10px] leading-none font-semibold text-primary-foreground tabular-nums"
          >
            {unread > 9 ? t("notifications.overflow") : unread}
          </span>
        ) : null}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex items-center justify-between gap-2">
            {t("notifications.label")}
            {unread ? (
              <button
                type="button"
                onClick={() => read.mutate([])}
                className="rounded-sm text-xs font-normal text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                {t("notifications.markAllRead")}
              </button>
            ) : null}
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        {(inbox.data?.items ?? []).length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">
            {t("notifications.empty")}
          </p>
        ) : (
          <DropdownMenuGroup>
            {inbox.data?.items.map((item) => (
              <DropdownMenuItem
                key={item.id}
                onClick={() => {
                  if (!item.read_at) read.mutate([item.id])
                  void navigate(href(item))
                }}
                className="items-start gap-2.5 py-2"
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "mt-1.5 size-2 shrink-0 rounded-full",
                    item.read_at ? "bg-transparent" : "bg-primary"
                  )}
                />
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm leading-snug">
                    {fillSlots(t(`notifications.${item.kind}`), {
                      actor: (
                        <span className="font-medium">{item.actor_name}</span>
                      ),
                      candidate: (
                        <span className="font-medium">{item.candidate}</span>
                      ),
                    })}
                  </span>
                  <span className="text-xs text-faint-foreground">
                    {relativeTime(item.created_at, i18n.language)}
                  </span>
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
