import { Link, type LinkProps } from "react-router"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function TextLink({ className, ...props }: LinkProps) {
  return (
    <Link
      className={cn(
        "rounded-sm font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        className
      )}
      {...props}
    />
  )
}

/** Only same-app paths: a crafted `?next=//evil.example` must not redirect off site. */
export function safeNext(next: string | null, fallback = "/"): string {
  return next && next.startsWith("/") && !next.startsWith("//")
    ? next
    : fallback
}

/** A navigation link that looks like a primary button. */
export function ButtonLink({ className, ...props }: LinkProps) {
  return (
    <Link className={cn(buttonVariants(), "w-full", className)} {...props} />
  )
}
