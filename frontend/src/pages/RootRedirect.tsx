import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/use-auth";
import { PageSpinner } from "@/components/ui/spinner";
import { homePathForRole } from "@/lib/routes";

export function RootRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <PageSpinner />;
  return <Navigate to={user ? homePathForRole(user.role) : "/login"} replace />;
}
