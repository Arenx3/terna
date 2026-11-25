import { useQuery } from "@tanstack/react-query"
import {
  ArrowLeftIcon,
  BanknoteIcon,
  CheckIcon,
  CopyIcon,
  PlusIcon,
} from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"

import { publicJobQuery } from "@/api/careers"
import { ApiError } from "@/api/errors"
import { CareersNotice } from "@/components/careers-notice"
import { ApplyForm } from "@/components/apply-form"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { moneyRange, shortDate } from "@/lib/format"
import { useJobFacts } from "@/pages/careers-page"

/** Embeds the JSON-LD safely: "<" can't close the script tag from inside a string. */
function StructuredData({ data }: { data: unknown }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c")
  return (
    <script
      type="application/ld+json"
      // The JSON comes from our API and "<" is escaped above.
      dangerouslySetInnerHTML={{ __html: json }}
    />
  )
}

export function PublicJobPage() {
  const { t, i18n } = useTranslation()
  const { slug = "", jobId = "" } = useParams()
  const page = useQuery(publicJobQuery(slug, jobId))
  const facts = useJobFacts()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 2400)
    return () => window.clearTimeout(timer)
  }, [copied])

  if (page.isPending) return <JobSkeleton />
  if (page.isError) {
    const missing = page.error instanceof ApiError && page.error.status === 404
    return <CareersNotice notFound={missing} />
  }

  const { job, company } = page.data
  const must = job.requirements.filter((item) => item.kind === "must")
  const nice = job.requirements.filter((item) => item.kind === "nice")
  const url = `${window.location.origin}/careers/${slug}/jobs/${job.id}`
  const summary = job.description.split("\n")[0]?.slice(0, 160) || job.title

  async function copyLink() {
    await navigator.clipboard.writeText(url)
    setCopied(true)
  }

  return (
    <article className="flex flex-col gap-10">
      <title>{`${job.title} · ${company.name}`}</title>
      <meta name="description" content={summary} />
      <meta property="og:title" content={`${job.title} · ${company.name}`} />
      <meta property="og:description" content={summary} />
      <link rel="canonical" href={url} />
      <StructuredData data={job.posting} />

      <Link
        to={`/careers/${slug}`}
        className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <ArrowLeftIcon aria-hidden="true" className="size-4" />
        {t("careers.allJobs")}
      </Link>

      <header className="flex flex-col gap-4">
        {job.department ? (
          <span className="text-xs font-medium tracking-wide text-faint-foreground uppercase">
            {job.department}
          </span>
        ) : null}
        <h1
          lang={job.language}
          className="text-[36px] leading-[1.08] font-semibold tracking-[-0.035em] text-balance"
        >
          {job.title}
        </h1>
        <p className="text-base text-muted-foreground">
          {facts(job).join(" · ")}
        </p>
        {job.salary ? (
          <p className="flex items-center gap-2 text-base font-medium">
            <BanknoteIcon aria-hidden="true" className="size-4 text-success" />
            {t("careers.salary", {
              range: moneyRange(
                job.salary.min,
                job.salary.max,
                job.salary.currency,
                i18n.language
              ),
              period: t(`careers.periods.${job.salary.period}`),
            })}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {job.published_at ? (
            <span className="text-sm text-faint-foreground">
              {t("careers.posted", {
                date: shortDate(job.published_at, i18n.language),
              })}
            </span>
          ) : null}
          <a href="#apply" className={buttonVariants({ size: "sm" })}>
            {t("careers.applyNow")}
          </a>
          <Button variant="outline" size="sm" onClick={() => void copyLink()}>
            {copied ? (
              <CheckIcon data-icon="inline-start" aria-hidden="true" />
            ) : (
              <CopyIcon data-icon="inline-start" aria-hidden="true" />
            )}
            {copied ? t("careers.copied") : t("careers.copyLink")}
          </Button>
          <span role="status" className="sr-only">
            {copied ? t("careers.copied") : ""}
          </span>
        </div>
      </header>

      <div lang={job.language} className="flex flex-col gap-10">
        {job.description ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold tracking-[-0.01em]">
              {t("careers.about")}
            </h2>
            <p className="text-base leading-7 whitespace-pre-line text-foreground/90">
              {job.description}
            </p>
          </section>
        ) : null}
        {must.length > 0 ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold tracking-[-0.01em]">
              {t("careers.mustHaves")}
            </h2>
            <ul className="flex flex-col gap-2.5">
              {must.map((item) => (
                <li key={item.text} className="flex gap-3 text-base leading-7">
                  <CheckIcon
                    aria-hidden="true"
                    className="mt-1.5 size-4 shrink-0 text-success"
                  />
                  {item.text}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {nice.length > 0 ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold tracking-[-0.01em]">
              {t("careers.niceToHaves")}
            </h2>
            <ul className="flex flex-col gap-2.5">
              {nice.map((item) => (
                <li
                  key={item.text}
                  className="flex gap-3 text-base leading-7 text-muted-foreground"
                >
                  <PlusIcon
                    aria-hidden="true"
                    className="mt-1.5 size-4 shrink-0 text-faint-foreground"
                  />
                  {item.text}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      <section
        id="apply"
        aria-labelledby="apply-title"
        className="flex scroll-mt-8 flex-col gap-5 border-t pt-10"
      >
        <div className="flex flex-col gap-1">
          <h2
            id="apply-title"
            className="text-xl font-semibold tracking-[-0.02em]"
          >
            {t("careers.apply.title")}
          </h2>
          <p className="text-muted-foreground">
            {t("careers.apply.description")}
          </p>
        </div>
        <ApplyForm slug={slug} jobId={job.id} jobTitle={job.title} />
      </section>
    </article>
  )
}

function JobSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-label={t("app.loading")}
      className="flex flex-col gap-6"
    >
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-10 w-96 max-w-full" />
      <Skeleton className="h-4 w-64" />
      <Skeleton className="mt-6 h-40 w-full" />
    </div>
  )
}
