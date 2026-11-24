// Source of truth for every visible string. `es.ts` must mirror these keys: TypeScript enforces it.
export const en = {
  app: {
    name: "Terna",
    tagline: "Applicant tracking with explainable screening.",
    loading: "Loading…",
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
  user: {
    menu: "Account menu",
    signedInAs: "Signed in as",
    logout: "Log out",
  },
  home: {
    title: "Welcome, {{name}}",
    description:
      "You're in {{company}}. Your workspace is on its way; meanwhile, this is the live health of the services behind it.",
  },
  auth: {
    email: "Email",
    password: "Password",
    backToLogin: "Back to log in",
    login: {
      title: "Log in to Terna",
      description: "Use the email you signed up with.",
      submit: "Log in",
      submitting: "Logging in…",
      forgot: "Forgot password?",
      noAccount: "New to Terna?",
      createAccount: "Create an account",
      resend: "Send a new confirmation link",
      resent:
        "If the address still needs confirming, a new link is on its way.",
    },
    signup: {
      title: "Create your company's workspace",
      description: "You'll be its first admin. You can invite your team later.",
      companyName: "Company name",
      fullName: "Your full name",
      email: "Work email",
      passwordHint: "At least 10 characters. Avoid common words and your name.",
      submit: "Create account",
      submitting: "Creating account…",
      haveAccount: "Already have an account?",
      login: "Log in",
    },
    checkEmail: {
      title: "Check your inbox",
      signup:
        "We sent a link to {{email}}. Open it to confirm your address, then log in.",
      reset:
        "If {{email}} has an account, we sent it a link to choose a new password. It expires in 2 hours.",
      noEmail: "Didn't get it? Check your spam folder, or send it again.",
      resend: "Send again",
      resent: "Sent. It can take a minute to arrive.",
    },
    verify: {
      verifying: "Confirming your email…",
      successTitle: "Email confirmed",
      successDescription: "Your account is ready. Log in to continue.",
      login: "Log in",
      failedTitle: "This link doesn't work",
      failedDescription:
        "It may have expired or been copied incomplete. Enter your email to get a new one.",
      resend: "Send a new link",
    },
    forgot: {
      title: "Reset your password",
      description:
        "Enter your account email and we'll send you a link to choose a new password.",
      submit: "Send reset link",
      submitting: "Sending…",
    },
    reset: {
      title: "Choose a new password",
      password: "New password",
      confirm: "Confirm new password",
      mismatch: "The passwords don't match.",
      submit: "Update password",
      submitting: "Updating…",
      successTitle: "Password updated",
      successDescription: "Log in with your new password.",
      login: "Log in",
      invalidTitle: "This reset link doesn't work",
      invalidDescription:
        "It may have expired or already been used. Request a new one.",
      requestNew: "Request a new link",
    },
  },
  errors: {
    invalid_credentials: "Email or password is incorrect.",
    email_not_verified:
      "Confirm your email before logging in. The link is in your inbox.",
    no_company:
      "This account isn't part of any company yet. Ask an admin to invite you.",
    invalid_link: "This link is invalid or has expired.",
    session_expired: "Your session expired. Log in again.",
    throttled: "Too many attempts. Wait a minute and try again.",
    server: "Something went wrong on our side. Try again in a moment.",
    network: "Can't reach Terna. Check your connection and try again.",
    fields: "Check the highlighted fields.",
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
