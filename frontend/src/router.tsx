import { createBrowserRouter } from "react-router"

import { AppShell } from "@/components/app-shell"
import { AuthLayout } from "@/components/auth-layout"
import { GuestOnly, RequireAuth } from "@/components/route-guards"
import { AcceptInvitationPage } from "@/pages/accept-invitation-page"
import { CheckEmailPage } from "@/pages/check-email-page"
import { ForgotPasswordPage } from "@/pages/forgot-password-page"
import { HomePage } from "@/pages/home-page"
import { LoginPage } from "@/pages/login-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { ResetPasswordPage } from "@/pages/reset-password-page"
import { SignupPage } from "@/pages/signup-page"
import { TeamPage } from "@/pages/team-page"
import { VerifyEmailPage } from "@/pages/verify-email-page"

export const router = createBrowserRouter([
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "team", element: <TeamPage /> },
        ],
      },
    ],
  },
  {
    element: <AuthLayout />,
    children: [
      {
        element: <GuestOnly />,
        children: [
          { path: "login", element: <LoginPage /> },
          { path: "signup", element: <SignupPage /> },
          { path: "forgot-password", element: <ForgotPasswordPage /> },
        ],
      },
      // Opened from email links, signed in or not.
      { path: "check-email", element: <CheckEmailPage /> },
      { path: "verify-email", element: <VerifyEmailPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
      { path: "invitations/accept", element: <AcceptInvitationPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
])
