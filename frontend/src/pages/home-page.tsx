import { Trans, useTranslation } from "react-i18next"

import { useSession } from "@/auth/session"
import { SystemStatus } from "@/components/system-status"
import { useDocumentTitle } from "@/hooks/use-document-title"

export function HomePage() {
  const { t } = useTranslation()
  const { session } = useSession()
  useDocumentTitle()

  const name = session?.user.full_name.split(" ")[0] ?? ""
  const company = session?.company.name ?? ""

  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-[32px] leading-tight font-semibold tracking-[-0.03em]">
          <Trans
            i18nKey="home.title"
            values={{ name }}
            components={{ mark: <span className="marker" /> }}
          />
        </h1>
        <p className="text-pretty text-muted-foreground">
          {t("home.description", { company })}
        </p>
      </div>
      <SystemStatus />
    </div>
  )
}
