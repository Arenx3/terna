import { useQuery } from "@tanstack/react-query"
import { ArrowRightIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"

import { careersQuery, type PublicJobSummary } from "@/api/careers"
import { ApiError } from "@/api/errors"
import { CareersNotice } from "@/components/careers-notice"
import { Skeleton } from "@/components/ui/skeleton"
import { countryName } from "@/lib/format"
import { fillSlots } from "@/lib/slots"

/** One line of facts about a job: where, how and what kind of contract. */
export function useJobFacts() {
  const { t, i18n } = useTranslation()
  return (job: PublicJobSummary) =>
    [
      [job.location, countryName(job.country, i18n.language)]
        .filter(Boolean)
        .join(", "),
      t(`jobs.workplace.${job.workplace}`),
      t(`jobs.employment.${job.employment}`),
    ].filter(Boolean)
}

export function CareersPage() {
  const { t } = useTranslation()
  const { slug = "" } = useParams()
  const careers = useQuery(careersQuery(slug))
  const facts = useJobFacts()
  const company = careers.data?.company.name

  if (careers.isPending) return <ListSkeleton />
  if (careers.isError) {
    const missing =
      careers.error instanceof ApiError && careers.error.status === 404
    return <CareersNotice notFound={missing} />
  }

  const { jobs } = careers.data
  const pageTitle = t("careers.workAt").replace("{company}", company ?? "")
  return (
    <div className="flex flex-col gap-12">
      {/* The company's page: its name leads the tab, not Terna's. */}
      <title>{pageTitle}</title>
      <meta
        name="description"
        content={t("careers.metaDescription", { company })}
      />
      <link
        rel="canonical"
        href={`${window.location.origin}/careers/${slug}`}
      />

      <div className="flex flex-col gap-3">
        <h1 className="text-[40px] leading-[1.05] font-semibold tracking-[-0.035em] text-balance">
          {fillSlots(t("careers.workAt"), {
            company: (
              <span className="marker" translate="no">
                {company}
              </span>
            ),
          })}
        </h1>
        <p className="text-base text-muted-foreground">
          {t("careers.openCount", { count: jobs.length })}
        </p>
      </div>

      {jobs.length === 0 ? (
        <p className="rounded-xl border border-dashed px-6 py-10 text-center text-muted-foreground">
          {t("careers.none")}
        </p>
      ) : (
        <ul className="flex flex-col border-t">
          {jobs.map((job) => (
            <li key={job.id} className="border-b">
              <Link
                to={`/careers/${slug}/jobs/${job.id}`}
                className="group flex items-center gap-6 rounded-md py-5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  {job.department ? (
                    <span className="text-xs font-medium tracking-wide text-faint-foreground uppercase">
                      {job.department}
                    </span>
                  ) : null}
                  <span
                    lang={job.language}
                    className="text-lg leading-snug font-medium text-balance"
                  >
                    {job.title}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {facts(job).join(" · ")}
                  </span>
                </div>
                <ArrowRightIcon
                  aria-hidden="true"
                  className="size-5 shrink-0 text-faint-foreground transition-transform duration-200 ease-out group-hover:translate-x-1 group-hover:text-foreground motion-reduce:transition-none"
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ListSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex flex-col gap-12"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="flex flex-col gap-6">
        {[0, 1, 2].map((row) => (
          <div key={row} className="flex flex-col gap-2">
            <Skeleton className="h-5 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
        ))}
      </div>
    </div>
  )
}
