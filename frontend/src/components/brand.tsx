import { useTranslation } from "react-i18next"

import { cn } from "@/lib/utils"

/**
 * Three marker strokes, stacked like a shortlist: the terna. Each finalist is
 * a highlighter pass, the first one fullest.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={cn("size-6 shrink-0", className)}
    >
      <g fill="var(--color-primary)" transform="rotate(-8 12 12)">
        <rect x="2.5" y="3.5" width="18" height="4.6" rx="2.3" />
        <rect x="4.5" y="9.7" width="15" height="4.6" rx="2.3" opacity="0.72" />
        <rect
          x="3.5"
          y="15.9"
          width="12"
          height="4.6"
          rx="2.3"
          opacity="0.45"
        />
      </g>
    </svg>
  )
}

export function Wordmark({ className }: { className?: string }) {
  const { t } = useTranslation()
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <BrandMark />
      <span
        className="font-heading text-[17px] font-semibold tracking-[-0.02em]"
        translate="no"
      >
        {t("app.name")}
      </span>
    </span>
  )
}
