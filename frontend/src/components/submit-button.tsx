import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

/** Full-width submit that shows progress and stays disabled while the request runs. */
export function SubmitButton({
  pending,
  label,
  pendingLabel,
}: {
  pending: boolean
  label: string
  pendingLabel: string
}) {
  return (
    <Button type="submit" className="w-full" disabled={pending}>
      {pending ? <Spinner data-icon="inline-start" aria-hidden="true" /> : null}
      {pending ? pendingLabel : label}
    </Button>
  )
}
