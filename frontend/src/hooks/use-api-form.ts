import { useMutation } from "@tanstack/react-query"
import { useEffect, useRef, type FormEvent } from "react"

import { ApiError } from "@/api/errors"

/**
 * An uncontrolled form posted to the API. Server field errors come back as
 * `fieldErrors`, and focus moves to the first invalid field after a failed submit.
 */
export function useApiForm<TResult>(
  submit: (values: Record<string, string>) => Promise<TResult>,
  options: {
    onSuccess?: (result: TResult, values: Record<string, string>) => void
  } = {}
) {
  const formRef = useRef<HTMLFormElement>(null)
  const mutation = useMutation({
    mutationFn: submit,
    onSuccess: (result, values) => options.onSuccess?.(result, values),
  })

  const fieldErrors =
    mutation.error instanceof ApiError ? mutation.error.fields : {}

  useEffect(() => {
    if (mutation.isError) {
      formRef.current
        ?.querySelector<HTMLElement>('[aria-invalid="true"]')
        ?.focus()
    }
  }, [mutation.isError, mutation.error])

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = Object.fromEntries(
      [...new FormData(event.currentTarget).entries()].map(([key, value]) => [
        key,
        String(value),
      ])
    )
    mutation.mutate(values)
  }

  return { formRef, onSubmit, mutation, fieldErrors }
}
