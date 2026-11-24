import { useQuery } from "@tanstack/react-query"
import {
  CircleAlertIcon,
  CircleCheckIcon,
  CircleXIcon,
  RefreshCwIcon,
} from "lucide-react"
import { useTranslation } from "react-i18next"

import { healthQuery, type Health, type ServiceName } from "@/api/health"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"

const SERVICES: ServiceName[] = ["database", "redis", "storage"]

export function SystemStatus() {
  const { t, i18n } = useTranslation()
  const { data, error, isPending, isFetching, refetch, dataUpdatedAt } =
    useQuery(healthQuery)

  const checkedAt =
    dataUpdatedAt > 0
      ? new Intl.DateTimeFormat(i18n.resolvedLanguage, {
          timeStyle: "medium",
        }).format(dataUpdatedAt)
      : null

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <CardTitle>{t("status.title")}</CardTitle>
        <CardDescription>{t("status.description")}</CardDescription>
        <CardAction>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? (
              <Spinner data-icon="inline-start" aria-hidden="true" />
            ) : (
              <RefreshCwIcon data-icon="inline-start" aria-hidden="true" />
            )}
            {t("status.refresh")}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error ? (
          <Alert variant="destructive">
            <CircleAlertIcon aria-hidden="true" />
            <AlertTitle>{t("status.unreachable.title")}</AlertTitle>
            <AlertDescription>
              {t("status.unreachable.description")}
            </AlertDescription>
          </Alert>
        ) : null}
        {isPending ? <ServiceListSkeleton /> : null}
        {data ? <ServiceList health={data} /> : null}
      </CardContent>
      {data ? (
        <CardFooter className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <p role="status" className="font-medium">
            {data.status === "ok"
              ? t("status.summaryOk")
              : t("status.summaryDegraded")}
          </p>
          {checkedAt ? (
            <p className="text-muted-foreground tabular-nums">
              {t("status.checkedAt", { time: checkedAt })}
            </p>
          ) : null}
        </CardFooter>
      ) : null}
    </Card>
  )
}

function ServiceList({ health }: { health: Health }) {
  const { t } = useTranslation()

  return (
    <ul className="flex flex-col divide-y">
      {SERVICES.map((service) => {
        const check = health.checks[service]
        const ok = check?.status === "ok"
        return (
          <li
            key={service}
            className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
          >
            <span className="truncate">{t(`status.services.${service}`)}</span>
            <span className="flex shrink-0 items-center gap-3">
              {check ? (
                <span className="text-sm text-muted-foreground tabular-nums">
                  {t("status.latency", { value: Math.round(check.latency_ms) })}
                </span>
              ) : null}
              <Badge variant={ok ? "secondary" : "destructive"}>
                {ok ? (
                  <CircleCheckIcon
                    data-icon="inline-start"
                    aria-hidden="true"
                  />
                ) : (
                  <CircleXIcon data-icon="inline-start" aria-hidden="true" />
                )}
                {ok ? t("status.ok") : t("status.error")}
              </Badge>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function ServiceListSkeleton() {
  return (
    <ul className="flex flex-col divide-y" aria-hidden="true">
      {SERVICES.map((service) => (
        <li
          key={service}
          className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
        >
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-5 w-24 rounded-full" />
        </li>
      ))}
    </ul>
  )
}
