import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

export type Choice<T extends string> = { value: T; label: string }

/** A labelled pick-one control over a fixed list of choices. */
export function ChoiceSelect<T extends string>({
  id,
  value,
  choices,
  onChange,
  label,
  disabled,
  invalid,
  describedBy,
  className,
}: {
  id?: string
  value: T
  choices: Choice<T>[]
  onChange: (value: T) => void
  /** Accessible name when no visible <label> points at `id`. */
  label?: string
  disabled?: boolean
  invalid?: boolean
  describedBy?: string
  className?: string
}) {
  return (
    <Select
      items={choices}
      value={value}
      onValueChange={(next) => next !== null && onChange(next as T)}
      disabled={disabled}
    >
      <SelectTrigger
        id={id}
        aria-label={label}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className={cn("w-full", className)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {choices.map((choice) => (
            <SelectItem key={choice.value} value={choice.value}>
              {choice.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
