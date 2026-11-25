/** Terna's Spanish speaks to Mexico first: 80,000 and "24 nov 2026". */
function regional(language: string) {
  return language.startsWith("es") ? "es-MX" : language
}

/** "12 Nov 2026" / "12 nov 2026". */
export function shortDate(iso: string, language: string) {
  return new Intl.DateTimeFormat(regional(language), {
    dateStyle: "medium",
  }).format(new Date(iso))
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

/** "MX" → "México" / "Mexico", in the reader's language. */
export function countryName(code: string, language: string) {
  try {
    return (
      new Intl.DisplayNames([language], { type: "region" }).of(code) ?? code
    )
  } catch {
    return code
  }
}

/** "$80,000–$110,000" in the reader's language, with the currency's own symbol. */
export function moneyRange(
  min: number,
  max: number,
  currency: string,
  language: string
) {
  return new Intl.NumberFormat(regional(language), {
    style: "currency",
    currency,
    currencyDisplay: "code",
    maximumFractionDigits: 0,
  }).formatRange(min, max)
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
]

/** "3 days ago" / "hace 3 días", in the reader's language. */
export function relativeTime(iso: string, language: string, now = Date.now()) {
  const seconds = (new Date(iso).getTime() - now) / 1000
  const format = new Intl.RelativeTimeFormat(regional(language), {
    numeric: "auto",
  })
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) {
      return format.format(Math.round(seconds / size), unit)
    }
  }
  // Under a minute: "now" / "ahora", not "this minute".
  return format.format(0, "second")
}
