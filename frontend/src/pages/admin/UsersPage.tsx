import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ShieldBan, ShieldCheck, Users as UsersIcon } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { adminApi } from "@/lib/api";

export function UsersPage() {
  const queryClient = useQueryClient();
  const { data: users, isLoading } = useQuery({ queryKey: ["admin", "users"], queryFn: () => adminApi.users() });

  const approveMutation = useMutation({
    mutationFn: (id: string) => adminApi.approveUser(id),
    onSuccess: () => {
      toast.success("User approved");
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
  const suspendMutation = useMutation({
    mutationFn: (id: string) => adminApi.suspendUser(id),
    onSuccess: () => {
      toast.success("User suspended");
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });

  return (
    <div>
      <PageHeader eyebrow="Accounts" title="Users" />

      {isLoading ? (
        <PageSpinner />
      ) : !users || users.length === 0 ? (
        <EmptyState icon={UsersIcon} title="No users yet" />
      ) : (
        <div className="space-y-2">
          {users.map((u) => (
            <Card key={u.id} className="flex items-center justify-between gap-4 p-3.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{u.full_name}</p>
                <p className="truncate text-xs text-ink-muted">{u.email}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Badge tone="neutral">{u.role}</Badge>
                {!u.is_approved && <Badge tone="warning">Pending</Badge>}
                {!u.is_approved && (
                  <Button size="sm" variant="outline" onClick={() => approveMutation.mutate(u.id)}>
                    <ShieldCheck className="h-3.5 w-3.5" /> Approve
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => suspendMutation.mutate(u.id)}>
                  <ShieldBan className="h-3.5 w-3.5 text-danger" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
