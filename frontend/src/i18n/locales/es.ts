import type { Resources } from "./en"

export const es: Resources = {
  app: {
    name: "Terna",
    tagline: "Reclutamiento con screening explicable.",
    loading: "Cargando…",
  },
  a11y: {
    skipToContent: "Saltar al contenido",
    close: "Cerrar",
    toggleSidebar: "Mostrar u ocultar la navegación",
    navigationDescription: "Navegación principal y tu cuenta.",
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
  nav: {
    label: "Principal",
    home: "Inicio",
    team: "Equipo",
    workspace: "Trabajo",
    company: "Empresa",
    search: "Busca o ve a…",
  },
  command: {
    title: "Menú de comandos",
    description: "Busca una página o una acción.",
    placeholder: "Escribe una página o una acción…",
    empty: "Nada coincide con eso.",
    pages: "Ir a",
    actions: "Acciones",
    companies: "Cambiar de empresa",
    preferences: "Preferencias",
    themeTo: "Usar tema {{name}}",
    languageTo: "Cambiar a {{name}}",
    invite: "Invitar a alguien",
    logout: "Cerrar sesión",
  },
  brand: {
    title: "De 300 CVs a tu terna,",
    highlight: "con evidencia.",
    lede: "Cada requisito apunta a la línea del CV que lo demuestra. La IA sugiere; tu equipo decide.",
    example: "Ejemplo sintético",
    role: "Senior Backend Engineer",
    candidate: "Candidato #A7F3",
    blind: "Revisión ciega",
    req1: "5+ años construyendo APIs en Python",
    ev1: "«Lideré la migración de 40 servicios a Python 3.12, 2019–2024.»",
    req2: "Kubernetes en producción",
    ev2: "«Operé los clústeres k8s del checkout a 3,000 pedidos por minuto.»",
    req3: "Inglés avanzado",
    ev3: "«Ponente en PyCon US 2025.»",
    summary: "3 de 3 obligatorios, cada uno con su prueba.",
  },
  roles: {
    admin: "Administrador",
    recruiter: "Reclutador",
    hiring_manager: "Responsable de contratación",
    interviewer: "Entrevistador",
  },
  company: {
    switch: "Cambiar de empresa",
    label: "Tus empresas",
  },
  team: {
    title: "Equipo",
    description:
      "Quién tiene acceso a {{company}} y qué puede hacer cada persona.",
    members: "Miembros",
    member: "Miembro",
    role: "Rol",
    you: "Tú",
    readOnly:
      "Solo los administradores pueden invitar, cambiar roles o quitar miembros.",
    changeRole: "Rol de {{name}}",
    remove: "Quitar",
    removeLabel: "Quitar a {{name}}",
    removeTitle: "¿Quitar a {{name}} de {{company}}?",
    removeDescription:
      "Pierde el acceso de inmediato. Puedes volver a invitarle después.",
    cancel: "Cancelar",
    confirmRemove: "Quitar miembro",
    invite: {
      title: "Invita a alguien",
      description:
        "Recibirá un correo con un enlace para unirse. Vence en 7 días.",
      email: "Correo",
      role: "Rol",
      submit: "Enviar invitación",
      submitting: "Enviando…",
      sent: "Invitación enviada a {{email}}.",
    },
    pending: {
      title: "Invitaciones pendientes",
      empty: "No hay invitaciones pendientes.",
      expires: "Vence el {{date}}",
      revoke: "Cancelar",
      revokeLabel: "Cancelar la invitación de {{email}}",
    },
  },
  invitation: {
    checking: "Revisando tu invitación…",
    title: "Únete a {{company}}",
    description: "Te invitaron como {{role}}, con {{email}}.",
    createAccount: "Crea tu cuenta para aceptar.",
    fullName: "Tu nombre completo",
    submit: "Aceptar y unirme",
    submitting: "Uniéndote…",
    loginToAccept:
      "Ya tienes una cuenta en Terna. Inicia sesión como {{email}} para aceptar.",
    login: "Iniciar sesión para aceptar",
    join: "Unirme a {{company}}",
    wrongAccount:
      "Esta invitación es para {{email}}, pero iniciaste sesión como {{current}}.",
    switchAccount: "Cerrar sesión y usar otra cuenta",
    invalidTitle: "Esta invitación no funciona",
    expired: "Venció. Pide a un administrador que te envíe una nueva.",
    used: "Ya se usó. Si fuiste tú, inicia sesión.",
    revoked: "Un administrador la canceló. Pídele que te invite de nuevo.",
    invalid: "El enlace no es válido o se copió incompleto.",
  },
  home: {
    title: "Hola, <mark>{{name}}</mark>",
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
    admin_required: "Solo los administradores pueden hacer esto.",
    not_member: "Ya no eres miembro de esta empresa.",
    last_admin:
      "Una empresa necesita al menos un administrador. Primero haz administrador a otra persona.",
    already_member: "Esta persona ya está en el equipo.",
    invitation_invalid: "Este enlace de invitación no es válido.",
    invitation_expired:
      "Esta invitación venció. Pide una nueva a un administrador.",
    invitation_used: "Esta invitación ya se usó.",
    invitation_revoked: "Esta invitación se canceló.",
    invitation_email_mismatch: "Esta invitación es para otro correo.",
    login_required: "Inicia sesión con el correo invitado para aceptar.",
    account_details_required:
      "Escribe tu nombre y una contraseña para crear tu cuenta.",
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
