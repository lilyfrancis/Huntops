import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/use-auth";
import { PageSpinner } from "@/components/ui/spinner";
import { homePathForRole } from "@/lib/routes";
import { LandingPage } from "@/pages/LandingPage";

export function RootRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <PageSpinner />;
  if (user) return <Navigate to={homePathForRole(user.role)} replace />;
  return <LandingPage />;
}
