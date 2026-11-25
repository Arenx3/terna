import { useParams } from "react-router"

import { CandidateProfile } from "@/components/profile/candidate-profile"
import { useDocumentTitle } from "@/hooks/use-document-title"

/** A candidate on a page of their own: where notifications lead interviewers,
 * who work on assigned candidates rather than on whole boards. */
export function ApplicationPage() {
  const { applicationId = "" } = useParams()
  useDocumentTitle()
  return (
    <div className="mx-auto w-full max-w-3xl">
      <CandidateProfile
        key={applicationId}
        applicationId={Number(applicationId)}
        Heading="h1"
      />
    </div>
  )
}
