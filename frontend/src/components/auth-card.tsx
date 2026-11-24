import type { ReactNode } from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useDocumentTitle } from "@/hooks/use-document-title"

/** The frame shared by the sign-in, sign-up and recovery screens. */
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
    <div className="flex flex-1 items-start justify-center pt-6 sm:pt-12">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h1 className="text-balance">{title}</h1>
          </CardTitle>
          {description ? (
            <CardDescription className="text-pretty">
              {description}
            </CardDescription>
          ) : null}
        </CardHeader>
        {children ? <CardContent>{children}</CardContent> : null}
        {footer ? (
          <CardFooter className="flex flex-wrap justify-center gap-1 text-sm text-muted-foreground">
            {footer}
          </CardFooter>
        ) : null}
      </Card>
    </div>
  )
}
