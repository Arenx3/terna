import { PlusIcon, XIcon } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import { useTranslation } from "react-i18next"

import type { RequirementKind } from "@/api/jobs"
import { SortableList } from "@/components/jobs/sortable-list"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

export type DraftRequirement = {
  key: string
  id?: number | null
  text: string
  kind: RequirementKind
}

const KINDS: RequirementKind[] = ["must", "nice"]

/** Must-have or nice-to-have, as a two-way switch that reads its state aloud. */
function KindSwitch({
  value,
  onChange,
  label,
  disabled,
}: {
  value: RequirementKind
  onChange: (kind: RequirementKind) => void
  label: string
  disabled?: boolean
}) {
  const { t } = useTranslation()
  return (
    <ToggleGroup
      value={[value]}
      onValueChange={(next) => {
        const kind = next[0] as RequirementKind | undefined
        if (kind) onChange(kind)
      }}
      aria-label={label}
      variant="outline"
      size="sm"
      spacing={0}
      disabled={disabled}
      className="ml-10 shrink-0 sm:ml-0"
    >
      {KINDS.map((kind) => (
        <ToggleGroupItem
          key={kind}
          value={kind}
          className="h-8 px-2.5 text-xs text-muted-foreground data-pressed:bg-secondary data-pressed:text-foreground"
        >
          {t(`jobs.editor.kind.${kind}`)}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

export function RequirementsEditor({
  value,
  onChange,
  disabled = false,
  invalid = false,
  describedBy,
}: {
  value: DraftRequirement[]
  onChange: (next: DraftRequirement[]) => void
  disabled?: boolean
  invalid?: boolean
  describedBy?: string
}) {
  const { t } = useTranslation()
  const newId = useId()
  const [text, setText] = useState("")
  const [kind, setKind] = useState<RequirementKind>("must")

  function update(key: string, patch: Partial<DraftRequirement>) {
    onChange(
      value.map((item) => (item.key === key ? { ...item, ...patch } : item))
    )
  }

  function add(event: FormEvent) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed) return
    onChange([...value, { key: crypto.randomUUID(), text: trimmed, kind }])
    setText("")
  }

  return (
    <div className="flex flex-col gap-3">
      {value.length > 0 ? (
        <SortableList
          items={value}
          onReorder={onChange}
          disabled={disabled}
          describe={(item, index) =>
            `${t("jobs.editor.requirement", { n: index + 1 })}: ${item.text}`
          }
          className="flex flex-col gap-1.5"
          renderItem={(item, index, handle) => (
            <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
              {handle}
              <Input
                value={item.text}
                onChange={(event) =>
                  update(item.key, { text: event.target.value })
                }
                aria-label={t("jobs.editor.requirement", { n: index + 1 })}
                aria-invalid={(invalid && !item.text.trim()) || undefined}
                aria-describedby={describedBy}
                maxLength={300}
                disabled={disabled}
                className="min-w-0 flex-1 basis-48"
              />
              <KindSwitch
                value={item.kind}
                onChange={(next) => update(item.key, { kind: next })}
                label={t("jobs.editor.kindOf", { n: index + 1 })}
                disabled={disabled}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() =>
                  onChange(value.filter((other) => other.key !== item.key))
                }
                aria-label={t("jobs.editor.removeRequirement", {
                  n: index + 1,
                })}
                disabled={disabled}
                className="text-faint-foreground hover:text-foreground"
              >
                <XIcon aria-hidden="true" />
              </Button>
            </div>
          )}
        />
      ) : (
        <p className="rounded-lg border border-dashed px-4 py-5 text-center text-sm text-muted-foreground">
          {t("jobs.editor.noRequirements")}
        </p>
      )}

      {disabled ? null : (
        // Its own form: Enter adds the requirement instead of saving the job.
        <form
          onSubmit={add}
          className="flex flex-wrap items-center gap-2 sm:flex-nowrap"
          aria-label={t("jobs.editor.newRequirement")}
        >
          <span
            aria-hidden="true"
            className="grid size-8 shrink-0 place-items-center text-faint-foreground"
          >
            <PlusIcon className="size-4" />
          </span>
          <Input
            id={newId}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={t("jobs.editor.requirementPlaceholder")}
            aria-label={t("jobs.editor.newRequirement")}
            maxLength={300}
            autoComplete="off"
            className="min-w-0 flex-1 basis-48"
          />
          <KindSwitch
            value={kind}
            onChange={setKind}
            label={t("jobs.editor.kindOf", { n: value.length + 1 })}
          />
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={!text.trim()}
          >
            {t("jobs.editor.addRequirement")}
          </Button>
        </form>
      )}
    </div>
  )
}
