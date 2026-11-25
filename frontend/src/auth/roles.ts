import { useSession } from "@/auth/session"

/**
 * The person's role in the active company, for hiding what they cannot do.
 * The API enforces the same rules: this only keeps the interface honest.
 */
export function useRole() {
  const { session } = useSession()
  const role = session?.company.role
  const isAdmin = role === "admin"
  const canManageJobs = isAdmin || role === "recruiter"
  return {
    role,
    isAdmin,
    canManageJobs,
    // Hiring managers see the jobs they own; interviewers only their interviews.
    canSeeJobs: canManageJobs || role === "hiring_manager",
  }
}
