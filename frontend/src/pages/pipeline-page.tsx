import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckIcon, CircleAlertIcon, LockIcon } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { errorMessage } from "@/api/errors"
import {
  pipelineTemplateQuery,
  savePipelineTemplate,
  type Stage,
} from "@/api/jobs"
import { useRole } from "@/auth/roles"
import { useSession } from "@/auth/session"
import { StagesEditor, type DraftStage } from "@/components/jobs/stages-editor"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useDocumentTitle } from "@/hooks/use-document-title"

function toDraft(stages: Stage[]): DraftStage[] {
  return stages.map((stage, index) => ({
    key: stage.id ? `stage-${stage.id}` : `stage-default-${index}`,
    id: stage.id,
    name: stage.name,
    kind: stage.kind,
  }))
}

export function PipelinePage() {
  const { t } = useTranslation()
  const { session } = useSession()
  const { isAdmin, canSeeJobs } = useRole()
  const companyId = session?.company.id ?? ""
  useDocumentTitle(t("pipeline.title"))
  const template = useQuery({
    ...pipelineTemplateQuery(companyId),
    enabled: canSeeJobs,
  })

  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.03em]">
          {t("pipeline.title")}
        </h1>
        <p className="text-pretty text-muted-foreground">
          {t("pipeline.description")}
        </p>
      </div>
      {!canSeeJobs ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <LockIcon aria-hidden="true" className="size-4" />
          {t("pipeline.adminOnly")}
        </p>
      ) : template.isPending ? (
        <Skeleton
          role="status"
          aria-label={t("app.loading")}
          className="h-80 max-w-2xl rounded-xl"
        />
      ) : template.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {t("jobs.loadError")}
        </p>
      ) : (
        <PipelineForm
          key={companyId}
          initial={toDraft(template.data.stages)}
          readOnly={!isAdmin}
        />
      )}
    </div>
  )
}

function PipelineForm({
  initial,
  readOnly,
}: {
  initial: DraftStage[]
  readOnly: boolean
}) {
  const { t } = useTranslation()
  const { session } = useSession()
  const queryClient = useQueryClient()
  const companyId = session?.company.id ?? ""
  const [stages, setStages] = useState(initial)
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: () =>
      savePipelineTemplate(
        stages.map((stage) => ({
          id: stage.id ?? null,
          name: stage.name.trim(),
          kind: stage.kind,
        }))
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(pipelineTemplateQuery(companyId).queryKey, data)
      setStages(toDraft(data.stages))
      setSaved(true)
    },
  })

  return (
    <section className="flex max-w-2xl flex-col gap-5 rounded-xl border bg-card p-5 sm:p-6">
      {readOnly ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <LockIcon aria-hidden="true" className="size-4" />
          {t("pipeline.adminOnly")}
        </p>
      ) : null}
      {save.isError ? (
        <Alert variant="destructive">
          <CircleAlertIcon aria-hidden="true" />
          <AlertDescription>{errorMessage(t, save.error)}</AlertDescription>
        </Alert>
      ) : null}
      <StagesEditor
        value={stages}
        onChange={(next) => {
          setStages(next)
          setSaved(false)
        }}
        disabled={readOnly}
      />
      {readOnly ? null : (
        <div className="flex items-center gap-3 border-t pt-5">
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? t("jobs.editor.saving") : t("pipeline.save")}
          </Button>
          <span role="status" className="text-[13px] text-muted-foreground">
            {saved ? (
              <span className="inline-flex items-center gap-1.5">
                <CheckIcon
                  aria-hidden="true"
                  className="size-3.5 text-success"
                />
                {t("pipeline.saved")}
              </span>
            ) : null}
          </span>
        </div>
      )}
    </section>
  )
}
