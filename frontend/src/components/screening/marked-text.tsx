import type { ReactNode } from "react"

/**
 * The marker over words inside a line: it keeps to the word, so the spaces and
 * the brackets around it stay visible ("de Kubernetes (GKE)").
 */
export const INLINE = "marker bg-transparent mx-0! px-[0.08em]!"

/** Spans as [start, end) pairs, sorted and merged where they touch. */
export function mergeSpans(spans: number[][]): [number, number][] {
  const out: [number, number][] = []
  for (const [start, end] of [...spans].sort((a, b) => a[0] - b[0])) {
    const last = out.at(-1)
    if (last && start <= last[1]) last[1] = Math.max(last[1], end)
    else out.push([start, end])
  }
  return out
}

/**
 * Text with the highlighter run over the evidence: the exact words a
 * requirement was met by, where they are in the line.
 */
export function MarkedText({
  text,
  spans,
  draw = false,
}: {
  text: string
  spans: number[][]
  /** Sweep the stroke in, once, the first time the evidence is shown. */
  draw?: boolean
}) {
  const parts: ReactNode[] = []
  let cursor = 0
  mergeSpans(spans).forEach(([start, end], index) => {
    if (start > cursor) parts.push(text.slice(cursor, start))
    parts.push(
      <mark
        key={start}
        className={draw ? `${INLINE} marker-draw` : INLINE}
        style={draw ? { animationDelay: `${index * 120}ms` } : undefined}
      >
        {text.slice(start, end)}
      </mark>
    )
    cursor = end
  })
  parts.push(text.slice(cursor))
  return <>{parts}</>
}
