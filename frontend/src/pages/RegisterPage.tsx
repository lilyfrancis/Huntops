import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChipGroup, humanize } from "@/components/ui/chip-group";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-client";
import { homePathForRole } from "@/lib/routes";
import type { JobLane, JobType, PreferenceOptions } from "@/lib/types";

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

const JOB_TYPE_LABEL: Record<JobType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
};

export function RegisterPage() {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const [step, setStep] = useState<"account" | "hunt">("account");

  const [markets, setMarkets] = useState<string[]>([]);
  const [lanes, setLanes] = useState<string[]>([]);
  const [jobTypes, setJobTypes] = useState<string[]>([]);

  /* Public: the picker has to be populated before anyone has an account, and
     the endpoint only ever returns the operator's list of live markets. */
  const { data: options } = useQuery({
    queryKey: ["preference-options", "public"],
    queryFn: () => api.get<PreferenceOptions>("/api/users/preferences/options", { skipAuth: true }),
    retry: false,
  });

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    trigger,
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
        preferences:
          values.role === "job_seeker"
            ? {
                target_markets: markets,
                lanes: lanes as JobLane[],
                job_types: jobTypes as JobType[],
              }
            : undefined,
      });
      toast.success("Welcome to HuntOps");
      navigate(homePathForRole(user.role), { replace: true });
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Something went wrong");
      setStep("account");
      toast.error("Registration failed");
    }
  };

  /* Employers have no feed to shape, so they submit straight from step one. */
  const goToHuntStep = async () => {
    if (await trigger()) setStep("hunt");
  };

  if (step === "hunt") {
    return (
      <AuthLayout>
        <button
          type="button"
          onClick={() => setStep("account")}
          className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back
        </button>

        <h2 className="mb-1 text-xl text-ink">What should we hunt for?</h2>
        <p className="mb-6 text-sm text-ink-muted">
          This shapes your feed from day one. You can change any of it later.
        </p>

        <div className="space-y-6">
          <div className="space-y-2">
            <Label>Where do you want to work?</Label>
            <ChipGroup
              aria-label="Target markets"
              options={(options?.markets ?? []).map((m) => ({ value: m, label: m }))}
              value={markets}
              onChange={setMarkets}
              emptyHint="No markets are live yet — you'll see every job we have until one is."
            />
          </div>

          <div className="space-y-2">
            <Label>What kind of work?</Label>
            <ChipGroup
              aria-label="Job families"
              options={(options?.lanes ?? []).map((l) => ({ value: l, label: humanize(l) }))}
              value={lanes}
              onChange={setLanes}
            />
          </div>

          <div className="space-y-2">
            <Label>Employment type</Label>
            <ChipGroup
              aria-label="Employment types"
              options={(options?.job_types ?? []).map((t) => ({
                value: t,
                label: JOB_TYPE_LABEL[t] ?? humanize(t),
              }))}
              value={jobTypes}
              onChange={setJobTypes}
            />
          </div>

          {serverError && <p className="text-sm text-danger">{serverError}</p>}

          <Button onClick={handleSubmit(onSubmit)} className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
          <p className="text-center text-xs text-ink-faint">
            Skip anything you're unsure about — an empty choice means "show me everything".
          </p>
        </div>
      </AuthLayout>
    );
  }

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

        {role === "job_seeker" ? (
          <Button type="button" onClick={goToHuntStep} className="w-full">
            Continue <ArrowRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        )}
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
