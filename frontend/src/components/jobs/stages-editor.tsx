import { LockIcon, PlusIcon, XIcon } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { MIDDLE_STAGE_KINDS, type StageKind } from "@/api/jobs"
import { ChoiceSelect } from "@/components/choice-select"
import { SortableList } from "@/components/jobs/sortable-list"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export type DraftStage = {
  key: string
  id?: number | null
  name: string
  kind: StageKind
}

export const MAX_STAGES = 12

/** A stage's own name, or its kind's label in the reader's language. */
export function useStageLabel() {
  const { t } = useTranslation()
  return (stage: { name: string; kind: StageKind }) =>
    stage.name.trim() || t(`stages.${stage.kind}`)
}

/**
 * The pipeline as a numbered rail. Applied opens it and Hired and Rejected
 * close it; those can be renamed but not moved. The stages in between are the
 * company's own: add, reorder, retype or remove them.
 */
export function StagesEditor({
  value,
  onChange,
  disabled = false,
}: {
  value: DraftStage[]
  onChange: (next: DraftStage[]) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const label = useStageLabel()
  const first = value[0]
  const middle = value.slice(1, -2)
  const last = value.slice(-2)

  function update(key: string, patch: Partial<DraftStage>) {
    onChange(
      value.map((stage) => (stage.key === key ? { ...stage, ...patch } : stage))
    )
  }

  function setMiddle(next: DraftStage[]) {
    onChange([first, ...next, ...last])
  }

  const nameInput = (stage: DraftStage, position: number) => (
    <Input
      value={stage.name}
      onChange={(event) => update(stage.key, { name: event.target.value })}
      placeholder={t(`stages.${stage.kind}`)}
      aria-label={t("jobs.editor.stageName", { n: position })}
      maxLength={60}
      disabled={disabled}
      className="order-last ml-[4.25rem] min-w-0 basis-full sm:order-none sm:ml-0 sm:flex-1 sm:basis-0"
    />
  )

  const fixedRow = (stage: DraftStage, position: number) => (
    <Row position={position}>
      <span
        className="grid size-8 shrink-0 place-items-center text-faint-foreground"
        title={t("jobs.editor.fixedStage")}
      >
        <LockIcon aria-hidden="true" className="size-3.5" />
        <span className="sr-only">{t("jobs.editor.fixedStage")}</span>
      </span>
      <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground sm:w-36 sm:flex-none">
        {t(`stages.${stage.kind}`)}
      </span>
      {nameInput(stage, position)}
      <span aria-hidden="true" className="hidden size-7 shrink-0 sm:block" />
    </Row>
  )

  if (!first) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        {fixedRow(first, 1)}
        <SortableList
          items={middle}
          onReorder={setMiddle}
          disabled={disabled}
          describe={(stage, index) => `${index + 2}. ${label(stage)}`}
          className="flex flex-col gap-1.5"
          renderItem={(stage, index, handle) => (
            <Row position={index + 2}>
              {handle}
              <ChoiceSelect
                value={stage.kind}
                onChange={(kind) => update(stage.key, { kind })}
                choices={MIDDLE_STAGE_KINDS.map((kind) => ({
                  value: kind,
                  label: t(`stages.${kind}`),
                }))}
                label={t("jobs.editor.stageKind", { n: index + 2 })}
                disabled={disabled}
                className="min-w-0 flex-1 sm:w-36 sm:flex-none"
              />
              {nameInput(stage, index + 2)}
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() =>
                  setMiddle(middle.filter((other) => other.key !== stage.key))
                }
                aria-label={t("jobs.editor.removeStage", { n: index + 2 })}
                disabled={disabled}
                className="text-faint-foreground hover:text-foreground"
              >
                <XIcon aria-hidden="true" />
              </Button>
            </Row>
          )}
        />
        {last.map((stage, index) => (
          <div key={stage.key}>
            {fixedRow(stage, middle.length + 2 + index)}
          </div>
        ))}
      </div>

      {disabled ? null : (
        <div className="flex items-center gap-3 pl-10">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={value.length >= MAX_STAGES}
            onClick={() =>
              setMiddle([
                ...middle,
                { key: crypto.randomUUID(), name: "", kind: "interview" },
              ])
            }
          >
            <PlusIcon data-icon="inline-start" aria-hidden="true" />
            {t("jobs.editor.addStage")}
          </Button>
          {value.length >= MAX_STAGES ? (
            <span className="text-xs text-muted-foreground">
              {t("jobs.editor.maxStages", { max: MAX_STAGES })}
            </span>
          ) : null}
        </div>
      )}
    </div>
  )
}

/** One stop on the rail: its number, then its controls. */
function Row({
  position,
  children,
}: {
  position: number
  children: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
      <span
        aria-hidden="true"
        className="w-5 shrink-0 text-right font-mono text-xs text-faint-foreground tabular-nums"
      >
        {position}
      </span>
      {children}
    </div>
  )
}
