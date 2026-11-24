import * as React from "react"

export const THEMES = ["dark", "light", "system"] as const
export type Theme = (typeof THEMES)[number]
type ResolvedTheme = "dark" | "light"

// Keep in sync with the inline script in index.html, which applies the theme before first paint.
export const THEME_STORAGE_KEY = "terna.theme"
const DEFAULT_THEME: Theme = "dark"
const COLOR_SCHEME_QUERY = "(prefers-color-scheme: dark)"
// Browser chrome color: matches --background in each theme (index.css).
const THEME_COLORS: Record<ResolvedTheme, string> = {
  dark: "#0a0a0a",
  light: "#ffffff",
}

type ThemeProviderState = {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const ThemeProviderContext = React.createContext<
  ThemeProviderState | undefined
>(undefined)

function isTheme(value: string | null): value is Theme {
  return THEMES.some((theme) => theme === value)
}

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isTheme(stored) ? stored : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme !== "system") {
    return theme
  }
  return window.matchMedia(COLOR_SCHEME_QUERY).matches ? "dark" : "light"
}

// Switching themes should be instant, not a cascade of color transitions.
function disableTransitionsTemporarily() {
  const style = document.createElement("style")
  style.appendChild(
    document.createTextNode(
      "*,*::before,*::after{-webkit-transition:none!important;transition:none!important}"
    )
  )
  document.head.appendChild(style)

  return () => {
    window.getComputedStyle(document.body)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => style.remove())
    })
  }
}

function applyTheme(theme: Theme) {
  const root = document.documentElement
  const resolved = resolveTheme(theme)
  if (root.classList.contains(resolved)) {
    return
  }

  const restoreTransitions = disableTransitionsTemporarily()
  root.classList.remove("light", "dark")
  root.classList.add(resolved)
  root.style.colorScheme = resolved
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", THEME_COLORS[resolved])
  restoreTransitions()
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = React.useState<Theme>(readStoredTheme)

  const setTheme = React.useCallback((nextTheme: Theme) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    } catch {
      // Private mode or storage disabled: the choice lasts for this visit only.
    }
    setThemeState(nextTheme)
  }, [])

  React.useEffect(() => {
    applyTheme(theme)

    if (theme !== "system") {
      return undefined
    }

    const mediaQuery = window.matchMedia(COLOR_SCHEME_QUERY)
    const handleChange = () => applyTheme("system")
    mediaQuery.addEventListener("change", handleChange)
    return () => mediaQuery.removeEventListener("change", handleChange)
  }, [theme])

  // Keep tabs in sync when the theme changes in another one.
  React.useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY) {
        setThemeState(isTheme(event.newValue) ? event.newValue : DEFAULT_THEME)
      }
    }
    window.addEventListener("storage", handleStorageChange)
    return () => window.removeEventListener("storage", handleStorageChange)
  }, [])

  const value = React.useMemo(() => ({ theme, setTheme }), [theme, setTheme])

  return (
    <ThemeProviderContext.Provider value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export function useTheme() {
  const context = React.useContext(ThemeProviderContext)
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return context
}
