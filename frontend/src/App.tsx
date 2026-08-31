import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/hooks/use-auth";
import { queryClient } from "@/lib/query-client";
import { ProtectedRoute } from "@/components/layout/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { PageSpinner } from "@/components/ui/spinner";

import { RootRedirect } from "@/pages/RootRedirect";

/*
  Route-level code splitting. The landing page is the first thing a visitor
  loads and it must not drag the entire authenticated app — every dashboard,
  chart, and dialog — down the wire with it. Only RootRedirect (which renders
  the landing page for logged-out visitors) is eager; everything else arrives
  when its route is actually visited.
*/
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("@/pages/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));

const JobFeedPage = lazy(() => import("@/pages/jobseeker/JobFeedPage").then((m) => ({ default: m.JobFeedPage })));
const MatchesPage = lazy(() => import("@/pages/jobseeker/MatchesPage").then((m) => ({ default: m.MatchesPage })));
const MomentumPage = lazy(() => import("@/pages/jobseeker/MomentumPage").then((m) => ({ default: m.MomentumPage })));
const ResumePage = lazy(() => import("@/pages/jobseeker/ResumePage").then((m) => ({ default: m.ResumePage })));
const ApplicationsPage = lazy(() => import("@/pages/jobseeker/ApplicationsPage").then((m) => ({ default: m.ApplicationsPage })));
const OutreachPage = lazy(() => import("@/pages/jobseeker/OutreachPage").then((m) => ({ default: m.OutreachPage })));
const InterviewsPage = lazy(() => import("@/pages/jobseeker/InterviewsPage").then((m) => ({ default: m.InterviewsPage })));
const NegotiationPage = lazy(() => import("@/pages/jobseeker/NegotiationPage").then((m) => ({ default: m.NegotiationPage })));
const DigestPage = lazy(() => import("@/pages/jobseeker/DigestPage").then((m) => ({ default: m.DigestPage })));
const IntegrationsPage = lazy(() => import("@/pages/jobseeker/IntegrationsPage").then((m) => ({ default: m.IntegrationsPage })));
const ProfilePage = lazy(() => import("@/pages/jobseeker/ProfilePage").then((m) => ({ default: m.ProfilePage })));

const MyJobsPage = lazy(() => import("@/pages/employer/MyJobsPage").then((m) => ({ default: m.MyJobsPage })));
const PostJobPage = lazy(() => import("@/pages/employer/PostJobPage").then((m) => ({ default: m.PostJobPage })));
const ApplicantsPage = lazy(() => import("@/pages/employer/ApplicantsPage").then((m) => ({ default: m.ApplicantsPage })));

const AnalyticsPage = lazy(() => import("@/pages/admin/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })));
const PendingJobsPage = lazy(() => import("@/pages/admin/PendingJobsPage").then((m) => ({ default: m.PendingJobsPage })));
const UsersPage = lazy(() => import("@/pages/admin/UsersPage").then((m) => ({ default: m.UsersPage })));
const OpsHealthPage = lazy(() => import("@/pages/admin/OpsHealthPage").then((m) => ({ default: m.OpsHealthPage })));

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Toaster theme="dark" position="top-right" toastOptions={{ className: "font-sans" }} />
          <Suspense fallback={<PageSpinner />}>
          <Routes>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route element={<ProtectedRoute roles={["job_seeker"]} />}>
              <Route element={<AppShell />}>
                <Route path="/app" element={<JobFeedPage />} />
                <Route path="/app/matches" element={<MatchesPage />} />
                <Route path="/app/momentum" element={<MomentumPage />} />
                <Route path="/app/resume" element={<ResumePage />} />
                <Route path="/app/applications" element={<ApplicationsPage />} />
                <Route path="/app/outreach" element={<OutreachPage />} />
                <Route path="/app/interviews" element={<InterviewsPage />} />
                <Route path="/app/negotiation" element={<NegotiationPage />} />
                <Route path="/app/digest" element={<DigestPage />} />
                <Route path="/app/integrations" element={<IntegrationsPage />} />
                <Route path="/app/profile" element={<ProfilePage />} />
              </Route>
            </Route>

            <Route element={<ProtectedRoute roles={["employer"]} />}>
              <Route element={<AppShell />}>
                <Route path="/employer" element={<MyJobsPage />} />
                <Route path="/employer/post" element={<PostJobPage />} />
                <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
              </Route>
            </Route>

            <Route element={<ProtectedRoute roles={["admin"]} />}>
              <Route element={<AppShell />}>
                <Route path="/admin" element={<AnalyticsPage />} />
                <Route path="/admin/jobs/pending" element={<PendingJobsPage />} />
                <Route path="/admin/users" element={<UsersPage />} />
                <Route path="/admin/ops" element={<OpsHealthPage />} />
              </Route>
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
