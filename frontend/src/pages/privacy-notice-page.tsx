import { useQuery } from "@tanstack/react-query"
import { ArrowLeftIcon } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"

import { careersQuery } from "@/api/careers"
import { CareersNotice } from "@/components/careers-notice"
import { Skeleton } from "@/components/ui/skeleton"

// Must match the version the API records with each consent.
export const PRIVACY_NOTICE_VERSION = "2026-11-25"

const SECTIONS = [
  ["who", "whoBody"],
  ["what", "whatBody"],
  ["why", "whyBody"],
  ["ai", "aiBody"],
  ["keep", "keepBody"],
  ["rights", "rightsBody"],
] as const

/** The privacy notice candidates accept when they apply (LFPDPPP / GDPR). */
export function PrivacyNoticePage() {
  const { t } = useTranslation()
  const { slug = "" } = useParams()
  const careers = useQuery(careersQuery(slug))

  if (careers.isPending) return <Skeleton className="h-96 w-full" />
  if (careers.isError) return <CareersNotice notFound />

  const company = careers.data.company.name
  return (
    <article className="flex flex-col gap-8">
      <title>{`${t("careers.privacy.title")} · ${company}`}</title>
      <Link
        to={`/careers/${slug}`}
        className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <ArrowLeftIcon aria-hidden="true" className="size-4" />
        {t("careers.allJobs")}
      </Link>
      <header className="flex flex-col gap-2">
        <h1 className="text-[32px] leading-tight font-semibold tracking-[-0.03em] text-balance">
          {t("careers.privacy.title")}
        </h1>
        <p className="text-sm text-faint-foreground">
          {t("careers.privacy.version", { version: PRIVACY_NOTICE_VERSION })}
        </p>
      </header>
      {SECTIONS.map(([title, body]) => (
        <section key={title} className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold tracking-[-0.01em]">
            {t(`careers.privacy.${title}`)}
          </h2>
          <p className="text-base leading-7 text-foreground/90">
            {t(`careers.privacy.${body}`, { company })}
          </p>
        </section>
      ))}
    </article>
  )
}
