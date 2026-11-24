// Source of truth for every visible string. `es.ts` must mirror these keys: TypeScript enforces it.
export const en = {
  app: {
    name: "Terna",
    tagline: "Applicant tracking with explainable screening.",
  },
  a11y: {
    skipToContent: "Skip to content",
  },
  theme: {
    label: "Theme",
    change: "Change theme",
    light: "Light",
    dark: "Dark",
    system: "System",
  },
  language: {
    label: "Language",
    change: "Change language",
    en: "English",
    es: "Español",
  },
  home: {
    title: "Terna is up and running",
    description:
      "The workspace is on its way. Meanwhile, this is the live health of the services behind it.",
  },
  status: {
    title: "System status",
    description: "The API checks each of its dependencies on every request.",
    refresh: "Check again",
    checkedAt: "Last checked {{time}}",
    summaryOk: "All systems operational",
    summaryDegraded: "Some services are down",
    ok: "Operational",
    error: "Down",
    latency: "{{value, number}} ms",
    services: {
      database: "Database",
      redis: "Queue and cache",
      storage: "File storage",
    },
    unreachable: {
      title: "Can't reach the API",
      description:
        "Make sure the stack is running with docker compose up, then check again.",
    },
  },
  notFound: {
    title: "Page not found",
    description: "The page you're looking for doesn't exist or was moved.",
    back: "Back to home",
  },
}

export type Resources = typeof en
