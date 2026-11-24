import type { Resources } from "./en"

export const es: Resources = {
  app: {
    name: "Terna",
    tagline: "Reclutamiento con screening explicable.",
  },
  a11y: {
    skipToContent: "Saltar al contenido",
  },
  theme: {
    label: "Tema",
    change: "Cambiar tema",
    light: "Claro",
    dark: "Oscuro",
    system: "Sistema",
  },
  language: {
    label: "Idioma",
    change: "Cambiar idioma",
    en: "English",
    es: "Español",
  },
  home: {
    title: "Terna está en marcha",
    description:
      "El espacio de trabajo viene en camino. Mientras tanto, este es el estado en vivo de los servicios que lo sostienen.",
  },
  status: {
    title: "Estado del sistema",
    description:
      "La API revisa cada una de sus dependencias en cada solicitud.",
    refresh: "Revisar de nuevo",
    checkedAt: "Última revisión: {{time}}",
    summaryOk: "Todos los sistemas funcionan",
    summaryDegraded: "Algunos servicios no responden",
    ok: "Funcionando",
    error: "Sin respuesta",
    latency: "{{value, number}} ms",
    services: {
      database: "Base de datos",
      redis: "Colas y caché",
      storage: "Almacenamiento",
    },
    unreachable: {
      title: "No se puede conectar con la API",
      description:
        "Verifica que el stack esté corriendo con docker compose up y vuelve a intentarlo.",
    },
  },
  notFound: {
    title: "No encontramos esta página",
    description: "La página que buscas no existe o cambió de lugar.",
    back: "Volver al inicio",
  },
}
