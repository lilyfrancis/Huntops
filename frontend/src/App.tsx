import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/hooks/use-auth";
import { queryClient } from "@/lib/query-client";
import { ProtectedRoute } from "@/components/layout/protected-route";
import { AppShell } from "@/components/layout/app-shell";

import { RootRedirect } from "@/pages/RootRedirect";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

import { JobFeedPage } from "@/pages/jobseeker/JobFeedPage";
import { MatchesPage } from "@/pages/jobseeker/MatchesPage";
import { MomentumPage } from "@/pages/jobseeker/MomentumPage";
import { ResumePage } from "@/pages/jobseeker/ResumePage";
import { ApplicationsPage } from "@/pages/jobseeker/ApplicationsPage";
import { OutreachPage } from "@/pages/jobseeker/OutreachPage";
import { InterviewsPage } from "@/pages/jobseeker/InterviewsPage";
import { NegotiationPage } from "@/pages/jobseeker/NegotiationPage";
import { DigestPage } from "@/pages/jobseeker/DigestPage";
import { IntegrationsPage } from "@/pages/jobseeker/IntegrationsPage";
import { ProfilePage } from "@/pages/jobseeker/ProfilePage";

import { MyJobsPage } from "@/pages/employer/MyJobsPage";
import { PostJobPage } from "@/pages/employer/PostJobPage";
import { ApplicantsPage } from "@/pages/employer/ApplicantsPage";

import { AnalyticsPage } from "@/pages/admin/AnalyticsPage";
import { PendingJobsPage } from "@/pages/admin/PendingJobsPage";
import { UsersPage } from "@/pages/admin/UsersPage";
import { OpsHealthPage } from "@/pages/admin/OpsHealthPage";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Toaster theme="dark" position="top-right" toastOptions={{ className: "font-sans" }} />
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
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
