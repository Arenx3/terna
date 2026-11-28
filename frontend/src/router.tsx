import { createBrowserRouter } from "react-router"

import { AppShell } from "@/components/app-shell"
import { AuthLayout } from "@/components/auth-layout"
import { CareersLayout } from "@/components/careers-layout"
import { ProfileSheet } from "@/components/profile/profile-sheet"
import { GuestOnly, RequireAuth } from "@/components/route-guards"
import { AcceptInvitationPage } from "@/pages/accept-invitation-page"
import { ApplicationPage } from "@/pages/application-page"
import { AuditPage } from "@/pages/audit-page"
import { CareersPage } from "@/pages/careers-page"
import { DictionaryPage } from "@/pages/dictionary-page"
import { EmailsPage } from "@/pages/emails-page"
import { CheckEmailPage } from "@/pages/check-email-page"
import { ForgotPasswordPage } from "@/pages/forgot-password-page"
import { HomePage } from "@/pages/home-page"
import { JobCandidatesPage } from "@/pages/job-candidates-page"
import { JobEditorPage } from "@/pages/job-editor-page"
import { JobsPage } from "@/pages/jobs-page"
import { LoginPage } from "@/pages/login-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { PipelinePage } from "@/pages/pipeline-page"
import { PrivacyNoticePage } from "@/pages/privacy-notice-page"
import { PublicJobPage } from "@/pages/public-job-page"
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
          { path: "jobs", element: <JobsPage /> },
          { path: "jobs/new", element: <JobEditorPage /> },
          { path: "jobs/:jobId", element: <JobEditorPage /> },
          {
            path: "jobs/:jobId/candidates",
            element: <JobCandidatesPage />,
            children: [{ path: ":applicationId", element: <ProfileSheet /> }],
          },
          { path: "applications/:applicationId", element: <ApplicationPage /> },
          { path: "team", element: <TeamPage /> },
          { path: "settings/pipeline", element: <PipelinePage /> },
          { path: "settings/audit", element: <AuditPage /> },
          { path: "settings/emails", element: <EmailsPage /> },
          { path: "settings/synonyms", element: <DictionaryPage /> },
        ],
      },
    ],
  },
  {
    // Public: no session needed, and none is restored.
    path: "careers/:slug",
    element: <CareersLayout />,
    children: [
      { index: true, element: <CareersPage /> },
      { path: "jobs/:jobId", element: <PublicJobPage /> },
      { path: "privacy", element: <PrivacyNoticePage /> },
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
