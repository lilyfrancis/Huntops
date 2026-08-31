import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";
import { homePathForRole } from "@/lib/routes";

const schema = z
  .object({
    full_name: z.string().min(2, "Enter your name"),
    email: z.string().email("Enter a valid email"),
    password: z
      .string()
      .min(8, "At least 8 characters")
      .regex(/[A-Z]/, "Needs an uppercase letter")
      .regex(/[a-z]/, "Needs a lowercase letter")
      .regex(/[0-9]/, "Needs a number"),
    role: z.enum(["job_seeker", "employer"]),
    company_name: z.string().optional(),
  })
  .refine((data) => data.role !== "employer" || !!data.company_name?.trim(), {
    message: "Company name is required for employers",
    path: ["company_name"],
  });
type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { role: "job_seeker" },
  });

  const role = watch("role");

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const user = await registerUser({
        email: values.email,
        password: values.password,
        full_name: values.full_name,
        role: values.role,
        company_name: values.role === "employer" ? values.company_name : undefined,
      });
      toast.success("Welcome to HuntOps");
      navigate(homePathForRole(user.role), { replace: true });
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Something went wrong");
      toast.error("Registration failed");
    }
  };

  return (
    <AuthLayout>
      <h2 className="mb-1 text-xl text-ink">Create your account</h2>
      <p className="mb-6 text-sm text-ink-muted">Free to start — upgrade when it's working for you.</p>

      <Tabs value={role} onValueChange={(v) => setValue("role", v as FormValues["role"])} className="mb-5">
        <TabsList className="w-full">
          <TabsTrigger value="job_seeker" className="flex-1">
            Job seeker
          </TabsTrigger>
          <TabsTrigger value="employer" className="flex-1">
            Employer
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="full_name">Full name</Label>
          <Input id="full_name" autoComplete="name" {...register("full_name")} />
          {errors.full_name && <p className="text-xs text-danger">{errors.full_name.message}</p>}
        </div>

        {role === "employer" && (
          <div className="space-y-1.5">
            <Label htmlFor="company_name">Company name</Label>
            <Input id="company_name" {...register("company_name")} />
            {errors.company_name && <p className="text-xs text-danger">{errors.company_name.message}</p>}
          </div>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
          {errors.email && <p className="text-xs text-danger">{errors.email.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
          {errors.password && <p className="text-xs text-danger">{errors.password.message}</p>}
        </div>

        {serverError && <p className="text-sm text-danger">{serverError}</p>}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Creating account…" : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-ink-muted">
        Already have an account?{" "}
        <Link to="/login" className="text-accent-strong hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
