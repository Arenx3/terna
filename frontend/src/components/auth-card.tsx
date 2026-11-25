import type { ReactNode } from "react"

import { useDocumentTitle } from "@/hooks/use-document-title"

/** The form column of the sign-in, sign-up and recovery screens: no card, the page is the surface. */
export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
}) {
  useDocumentTitle(title)

  return (
    <div className="flex w-full max-w-[380px] flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-[28px] leading-[1.15] font-semibold tracking-[-0.025em]">
          {title}
        </h1>
        {description ? (
          <p className="text-[15px] leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {children}
      {footer ? (
        <div className="flex flex-wrap gap-1 text-sm text-muted-foreground">
          {footer}
        </div>
      ) : null}
    </div>
  )
}
