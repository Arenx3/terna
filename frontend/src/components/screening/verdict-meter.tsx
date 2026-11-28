import { useTranslation } from "react-i18next"

import type { ScreeningSummary, Verdict } from "@/api/screening"
import { cn } from "@/lib/utils"

type Counts = Omit<ScreeningSummary, "status">

/** Segments in reading order: must-haves first, then nice-to-haves, best first. */
function segments(
  counts: Counts
): { kind: "must" | "nice"; verdict: Verdict }[] {
  const of = (
    kind: "must" | "nice",
    total: number,
    meets: number,
    partial: number
  ) =>
    Array.from({ length: total }, (_, index) => ({
      kind,
      verdict: (index < meets
        ? "meets"
        : index < meets + partial
          ? "partial"
          : "no_evidence") as Verdict,
    }))
  return [
    ...of("must", counts.must_total, counts.must_meets, counts.must_partial),
    ...of("nice", counts.nice_total, counts.nice_meets, counts.nice_partial),
  ]
}

/** One requirement's share of the bar: the highlighter's fill for what it meets. */
export const VERDICT_FILL: Record<Verdict, string> = {
  meets: "bg-primary",
  // Hatched, so partly met never depends on telling two shades apart.
  partial:
    "bg-foreground/10 bg-[repeating-linear-gradient(135deg,var(--color-primary)_0_2px,transparent_2px_4px)]",
  no_evidence: "bg-foreground/10",
}

/** What the counts say, in words, for screen readers and tooltips. */
export function useSummaryLabel() {
  const { t } = useTranslation()
  return (counts: Counts) =>
    [
      t("screening.summary.must", {
        meets: counts.must_meets,
        total: counts.must_total,
        partial: counts.must_partial,
      }),
      counts.nice_total
        ? t("screening.summary.nice", {
            meets: counts.nice_meets,
            total: counts.nice_total,
            partial: counts.nice_partial,
          })
        : null,
    ]
      .filter(Boolean)
      .join(" ")
}

/**
 * The screening at a glance: one segment per requirement, as wide as its weight
 * (a must-have counts twice), filled by its verdict. The bar is the weighted
 * sum the profile spells out; the figures beside it carry the exact counts.
 */
export function VerdictMeter({
  counts,
  className,
  size = "sm",
}: {
  counts: Counts
  className?: string
  size?: "sm" | "md"
}) {
  const label = useSummaryLabel()
  const parts = segments(counts)
  if (parts.length === 0) return null
  return (
    <span
      role="img"
      aria-label={label(counts)}
      className={cn("flex items-center gap-0.5", className)}
    >
      {parts.map((part, index) => (
        <span
          key={index}
          className={cn(
            "rounded-[2px]",
            size === "sm" ? "h-1.5" : "h-2",
            part.kind === "must" ? "flex-[2]" : "flex-1",
            // A wider gap where the nice-to-haves start.
            part.kind === "nice" &&
              parts[index - 1]?.kind === "must" &&
              "ml-1.5",
            VERDICT_FILL[part.verdict]
          )}
        />
      ))}
    </span>
  )
}
