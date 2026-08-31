import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { jobsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { ExperienceLevel, JobType } from "@/lib/types";

const schema = z.object({
  title: z.string().min(3, "At least 3 characters"),
  description: z.string().min(20, "At least 20 characters"),
  requirements: z.string().optional(),
  location: z.string().min(1, "Required"),
  salary_range: z.string().optional(),
  job_type: z.enum(["full_time", "part_time", "contract", "internship"]),
  experience_level: z.enum(["entry", "mid", "senior", "lead", "executive"]),
});
type FormValues = z.infer<typeof schema>;

export function PostJobPage() {
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { job_type: "full_time" as JobType, experience_level: "mid" as ExperienceLevel },
  });

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      jobsApi.create({
        ...values,
        requirements: values.requirements ? values.requirements.split(",").map((r) => r.trim()).filter(Boolean) : [],
      }),
    onSuccess: () => {
      toast.success("Job submitted — pending admin approval");
      navigate("/employer");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't post job"),
  });

  return (
    <div>
      <PageHeader eyebrow="New listing" title="Post a job" description="Goes live once an admin approves it." />

      <Card className="max-w-xl">
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))}>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-xs text-danger">{errors.title.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={5} {...register("description")} />
              {errors.description && <p className="text-xs text-danger">{errors.description.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="requirements">Requirements (comma-separated)</Label>
              <Input id="requirements" placeholder="Python, Salesforce, HubSpot" {...register("requirements")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="location">Location</Label>
                <Input id="location" placeholder="Remote" {...register("location")} />
                {errors.location && <p className="text-xs text-danger">{errors.location.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="salary_range">Salary range</Label>
                <Input id="salary_range" placeholder="$90k–$120k" {...register("salary_range")} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Job type</Label>
                <Select value={watch("job_type")} onValueChange={(v) => setValue("job_type", v as JobType)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full_time">Full-time</SelectItem>
                    <SelectItem value="part_time">Part-time</SelectItem>
                    <SelectItem value="contract">Contract</SelectItem>
                    <SelectItem value="internship">Internship</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Experience level</Label>
                <Select
                  value={watch("experience_level")}
                  onValueChange={(v) => setValue("experience_level", v as ExperienceLevel)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="entry">Entry</SelectItem>
                    <SelectItem value="mid">Mid</SelectItem>
                    <SelectItem value="senior">Senior</SelectItem>
                    <SelectItem value="lead">Lead</SelectItem>
                    <SelectItem value="executive">Executive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Posting…" : "Post job"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
