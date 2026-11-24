import { useSession } from "@/auth/session"

/**
 * The person's role in the active company, for hiding what they cannot do.
 * The API enforces the same rules: this only keeps the interface honest.
 */
export function useRole() {
  const { session } = useSession()
  const role = session?.company.role
  return { role, isAdmin: role === "admin" }
}
