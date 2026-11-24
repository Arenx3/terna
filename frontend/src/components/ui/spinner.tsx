import { cn } from "cn"
import { Loader2Icon } from "lucide-react"

// No built-in label: pass a translated `aria-label`, or `aria-hidden` when the parent already says it.
function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    <Loader2Icon
      data-slot="spinner"
      role="status"
      className={cn("size-4 animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }
