import { useId } from "react"
import { useNavigate, useParams } from "react-router"

import { CandidateProfile } from "@/components/profile/candidate-profile"
import { Sheet, SheetContent } from "@/components/ui/sheet"

/**
 * A candidate over their job's board. It has its own URL, so it can be shared
 * or reloaded; closing it goes back to the board, focus and all.
 */
export function ProfileSheet() {
  const { jobId = "", applicationId = "" } = useParams()
  const navigate = useNavigate()
  const headingId = useId()

  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) void navigate(`/jobs/${jobId}/candidates`)
      }}
    >
      <SheetContent
        side="right"
        aria-labelledby={headingId}
        className="w-full overflow-y-auto p-6 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl"
      >
        {/* Labelled by the candidate's name, the panel's visible heading. */}
        <CandidateProfile
          key={applicationId}
          applicationId={Number(applicationId)}
          headingId={headingId}
        />
      </SheetContent>
    </Sheet>
  )
}
