/** "12 Nov 2026" / "12 nov 2026". */
export function shortDate(iso: string, language: string) {
  return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(
    new Date(iso)
  )
}

/** Initials for an avatar: "Ana Pérez" → "AP". */
export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("")
}
