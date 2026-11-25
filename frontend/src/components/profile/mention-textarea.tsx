import { useId, useRef, useState, type KeyboardEvent } from "react"
import { useTranslation } from "react-i18next"

import type { Teammate } from "@/api/profile"
import { Textarea } from "@/components/ui/textarea"
import { initials } from "@/lib/format"
import { cn } from "@/lib/utils"

const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()

/** The "@que" being typed right before the caret, if any. */
function mentionAt(text: string, caret: number) {
  const match = /(^|\s)@([\p{L}' ]{0,30})$/u.exec(text.slice(0, caret))
  return match ? { start: caret - match[2].length - 1, query: match[2] } : null
}

/** People named in a comment: whoever's "@Full Name" is still in the text. */
export function mentionedIn(text: string, people: Teammate[]) {
  return people
    .filter((person) => text.includes(`@${person.full_name}`))
    .map((person) => person.id)
}

/**
 * A textarea that suggests teammates after "@". It is a combobox: arrows move
 * through the suggestions, Enter or Tab picks one, Escape closes the list.
 */
export function MentionTextarea({
  id,
  value,
  onChange,
  people,
  label,
  describedBy,
  placeholder,
  disabled,
  onSubmit,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  people: Teammate[]
  label: string
  describedBy?: string
  placeholder?: string
  disabled?: boolean
  onSubmit?: () => void
}) {
  const { t } = useTranslation()
  const listId = useId()
  const ref = useRef<HTMLTextAreaElement>(null)
  const [mention, setMention] = useState<{
    start: number
    query: string
  } | null>(null)
  const [active, setActive] = useState(0)

  const suggestions = mention
    ? people.filter((person) =>
        fold(person.full_name).includes(fold(mention.query.trim()))
      )
    : []
  const open = suggestions.length > 0

  function track(text: string, caret: number) {
    setMention(mentionAt(text, caret))
    setActive(0)
  }

  function pick(person: Teammate) {
    if (!mention) return
    const caret = ref.current?.selectionStart ?? value.length
    const inserted = `@${person.full_name} `
    const next = value.slice(0, mention.start) + inserted + value.slice(caret)
    onChange(next)
    setMention(null)
    const position = mention.start + inserted.length
    requestAnimationFrame(() =>
      ref.current?.setSelectionRange(position, position)
    )
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (open) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault()
        const step = event.key === "ArrowDown" ? 1 : -1
        setActive(
          (current) =>
            (current + step + suggestions.length) % suggestions.length
        )
        return
      }
      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault()
        pick(suggestions[active])
        return
      }
      if (event.key === "Escape") {
        event.preventDefault()
        event.stopPropagation() // close the list, not the panel around it
        setMention(null)
        return
      }
    }
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      onSubmit?.()
    }
  }

  return (
    <div className="relative">
      <Textarea
        ref={ref}
        id={id}
        value={value}
        rows={3}
        maxLength={5000}
        placeholder={placeholder}
        disabled={disabled}
        aria-label={label}
        aria-describedby={describedBy}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        onChange={(event) => {
          onChange(event.target.value)
          track(event.target.value, event.target.selectionStart)
        }}
        onKeyDown={onKeyDown}
        onClick={(event) => track(value, event.currentTarget.selectionStart)}
        onBlur={() => setMention(null)}
        className="min-h-20 resize-y leading-relaxed"
      />
      <ul
        id={listId}
        role="listbox"
        aria-label={t("profile.mentionList")}
        hidden={!open}
        className="absolute top-full left-0 z-20 mt-1 w-64 overflow-hidden rounded-lg border bg-popover p-1 shadow-sm"
      >
        {suggestions.map((person, index) => (
          <li
            key={person.id}
            id={`${listId}-${index}`}
            role="option"
            aria-selected={index === active}
            // Keep focus in the textarea: pick on mouse down, before the blur.
            onMouseDown={(event) => {
              event.preventDefault()
              pick(person)
            }}
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm",
              index === active && "bg-accent"
            )}
          >
            <span
              aria-hidden="true"
              className="grid size-5 place-items-center rounded-full border bg-muted text-[9px] font-medium"
            >
              {initials(person.full_name)}
            </span>
            {person.full_name}
          </li>
        ))}
      </ul>
    </div>
  )
}
