import { useId, type ComponentProps } from "react"

import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type TextFieldProps = Omit<ComponentProps<typeof Input>, "id" | "name"> & {
  name: string
  label: string
  description?: string
  errors?: string[]
}

/** Label, input, hint and server errors wired together for screen readers. */
export function TextField({
  name,
  label,
  description,
  errors = [],
  ...inputProps
}: TextFieldProps) {
  const id = useId()
  const invalid = errors.length > 0
  const describedBy =
    [description ? `${id}-description` : null, invalid ? `${id}-error` : null]
      .filter(Boolean)
      .join(" ") || undefined

  return (
    <Field data-invalid={invalid || undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        name={name}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        {...inputProps}
      />
      {description ? (
        <FieldDescription id={`${id}-description`}>
          {description}
        </FieldDescription>
      ) : null}
      <FieldError
        id={`${id}-error`}
        errors={errors.map((message) => ({ message }))}
      />
    </Field>
  )
}
