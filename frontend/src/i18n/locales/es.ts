import type { Resources } from "./en"

export const es: Resources = {
  app: {
    name: "Terna",
    tagline: "Reclutamiento con screening explicable.",
    loading: "Cargando…",
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
  user: {
    menu: "Menú de la cuenta",
    signedInAs: "Sesión iniciada como",
    logout: "Cerrar sesión",
  },
  home: {
    title: "Hola, {{name}}",
    description:
      "Estás en {{company}}. Tu espacio de trabajo viene en camino; mientras tanto, este es el estado en vivo de los servicios que lo sostienen.",
  },
  auth: {
    email: "Correo",
    password: "Contraseña",
    backToLogin: "Volver a iniciar sesión",
    login: {
      title: "Inicia sesión en Terna",
      description: "Usa el correo con el que te registraste.",
      submit: "Iniciar sesión",
      submitting: "Iniciando sesión…",
      forgot: "¿Olvidaste tu contraseña?",
      noAccount: "¿Eres nuevo en Terna?",
      createAccount: "Crea una cuenta",
      resend: "Enviar un nuevo enlace de confirmación",
      resent:
        "Si el correo aún necesita confirmarse, va en camino un enlace nuevo.",
    },
    signup: {
      title: "Crea el espacio de tu empresa",
      description:
        "Serás su primer administrador. Podrás invitar a tu equipo después.",
      companyName: "Nombre de la empresa",
      fullName: "Tu nombre completo",
      email: "Correo de trabajo",
      passwordHint:
        "Al menos 10 caracteres. Evita palabras comunes y tu nombre.",
      submit: "Crear cuenta",
      submitting: "Creando cuenta…",
      haveAccount: "¿Ya tienes una cuenta?",
      login: "Inicia sesión",
    },
    checkEmail: {
      title: "Revisa tu correo",
      signup:
        "Enviamos un enlace a {{email}}. Ábrelo para confirmar tu correo y después inicia sesión.",
      reset:
        "Si {{email}} tiene una cuenta, le enviamos un enlace para elegir una contraseña nueva. Vence en 2 horas.",
      noEmail: "¿No te llegó? Revisa la carpeta de spam o envíalo de nuevo.",
      resend: "Enviar de nuevo",
      resent: "Enviado. Puede tardar un minuto en llegar.",
    },
    verify: {
      verifying: "Confirmando tu correo…",
      successTitle: "Correo confirmado",
      successDescription: "Tu cuenta está lista. Inicia sesión para continuar.",
      login: "Iniciar sesión",
      failedTitle: "Este enlace no funciona",
      failedDescription:
        "Puede que haya vencido o que se haya copiado incompleto. Escribe tu correo para recibir uno nuevo.",
      resend: "Enviar un enlace nuevo",
    },
    forgot: {
      title: "Restablece tu contraseña",
      description:
        "Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una contraseña nueva.",
      submit: "Enviar enlace",
      submitting: "Enviando…",
    },
    reset: {
      title: "Elige una contraseña nueva",
      password: "Contraseña nueva",
      confirm: "Confirma la contraseña nueva",
      mismatch: "Las contraseñas no coinciden.",
      submit: "Actualizar contraseña",
      submitting: "Actualizando…",
      successTitle: "Contraseña actualizada",
      successDescription: "Inicia sesión con tu contraseña nueva.",
      login: "Iniciar sesión",
      invalidTitle: "Este enlace de restablecimiento no funciona",
      invalidDescription:
        "Puede que haya vencido o que ya se haya usado. Pide uno nuevo.",
      requestNew: "Pedir un enlace nuevo",
    },
  },
  errors: {
    invalid_credentials: "El correo o la contraseña no son correctos.",
    email_not_verified:
      "Confirma tu correo antes de iniciar sesión. El enlace está en tu bandeja.",
    no_company:
      "Esta cuenta todavía no pertenece a ninguna empresa. Pide a un administrador que te invite.",
    invalid_link: "Este enlace no es válido o ya venció.",
    session_expired: "Tu sesión venció. Inicia sesión de nuevo.",
    throttled: "Demasiados intentos. Espera un minuto y vuelve a intentarlo.",
    server: "Algo falló de nuestro lado. Inténtalo de nuevo en un momento.",
    network:
      "No se puede conectar con Terna. Revisa tu conexión e inténtalo de nuevo.",
    fields: "Revisa los campos marcados.",
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
