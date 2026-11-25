import { CheckIcon, EyeOffIcon } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Wordmark } from "@/components/brand"

const REQUIREMENTS = [
  { requirement: "brand.req1", evidence: "brand.ev1" },
  { requirement: "brand.req2", evidence: "brand.ev2" },
  { requirement: "brand.req3", evidence: "brand.ev3" },
] as const

/**
 * The product's promise, shown working: a (synthetic) screening where each
 * requirement gets highlighted with the line of the résumé that proves it.
 */
export function EvidencePanel() {
  const { t } = useTranslation()

  return (
    <aside className="relative hidden flex-col justify-between overflow-hidden border-r bg-muted/50 p-12 lg:flex xl:p-16">
      <Wordmark />

      <div className="flex max-w-[30rem] flex-col">
        <p className="font-heading text-[2.75rem] leading-[1.04] font-semibold tracking-[-0.035em] text-balance">
          {t("brand.title")}{" "}
          <span className="marker marker-draw [animation-delay:250ms]">
            {t("brand.highlight")}
          </span>
        </p>
        <p className="mt-5 max-w-[26rem] text-[15px] leading-relaxed text-muted-foreground">
          {t("brand.lede")}
        </p>

        <figure className="mt-10 rounded-xl border bg-card shadow-[0_1px_0_0_var(--color-border)]">
          <header className="flex items-center justify-between gap-4 border-b px-5 py-3.5">
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-medium">
                {t("brand.role")}
              </span>
              <span className="font-mono text-xs text-faint-foreground">
                {t("brand.candidate")}
              </span>
            </div>
            <span className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs text-muted-foreground">
              <EyeOffIcon aria-hidden="true" className="size-3.5" />
              {t("brand.blind")}
            </span>
          </header>
          <ol className="flex flex-col gap-4 px-5 py-4">
            {REQUIREMENTS.map((item, index) => (
              <li key={item.requirement} className="flex gap-3">
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-success/15 text-success">
                  <CheckIcon aria-hidden="true" className="size-3.5" />
                </span>
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="text-sm font-medium">
                    {t(item.requirement)}
                  </span>
                  <span className="text-sm leading-relaxed text-muted-foreground">
                    <span
                      className="marker marker-draw"
                      style={{ animationDelay: `${700 + index * 380}ms` }}
                    >
                      {t(item.evidence)}
                    </span>
                  </span>
                </div>
              </li>
            ))}
          </ol>
          <figcaption className="flex items-center justify-between gap-4 border-t px-5 py-3 text-xs text-muted-foreground">
            <span>{t("brand.summary")}</span>
            <span className="flex gap-1" aria-hidden="true">
              <span className="size-2 rounded-full bg-primary" />
              <span className="size-2 rounded-full bg-primary" />
              <span className="size-2 rounded-full bg-primary" />
            </span>
          </figcaption>
        </figure>
        <p className="mt-3 text-xs text-faint-foreground">
          {t("brand.example")}
        </p>
      </div>

      <span aria-hidden="true" />
    </aside>
  )
}
