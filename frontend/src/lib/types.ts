// Mirrors backend/app/schemas/*.py and app/models/enums.py exactly.
// Keep these in sync by hand — there's no shared schema generation yet.

export type UserRole = "job_seeker" | "employer" | "admin";
export type SubscriptionTier = "free" | "pro" | "elite";
export type JobStatus = "pending" | "active" | "rejected" | "closed";
export type JobType = "full_time" | "part_time" | "contract" | "internship";
export type ExperienceLevel = "entry" | "mid" | "senior" | "lead" | "executive";
export type ApplicationStatus = "pending" | "reviewed" | "interviewing" | "offered" | "rejected" | "withdrawn";
export type OutreachStatus = "sent" | "draft_no_contact" | "failed";
export type JobLane =
  | "engineering"
  | "product"
  | "design"
  | "gtm"
  | "revops"
  | "marketing"
  | "sales"
  | "automation"
  | "operations"
  | "leadership"
  | "customer_success"
  | "finance"
  | "hr"
  | "other";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  company_name: string | null;
  home_market: string | null;
  positioning_statement: string | null;
  subscription_tier: SubscriptionTier;
  ai_credits: number;
  is_approved: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Job {
  id: string;
  employer_id: string | null;
  employer_name: string | null;
  company_name: string | null;
  title: string;
  description: string;
  requirements: string[];
  location: string;
  salary_range: string | null;
  job_type: JobType;
  experience_level: ExperienceLevel;
  status: JobStatus;
  rejection_reason: string | null;
  is_featured: boolean;
  application_count: number;
  source: string;
  source_url: string | null;
  lane: JobLane | null;
  is_remote: boolean;
  restricted_to: string | null;
  ghost_score: number | null;
  ghost_flags: string[];
  ghost_band: GhostBand;
  created_at: string;
}

export type GhostBand = "unchecked" | "clean" | "caution" | "likely_ghost";

export interface Application {
  id: string;
  job_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  cover_letter: string | null;
  status: ApplicationStatus;
  ai_match_score: number | null;
  created_at: string;
}

export interface JobMatch {
  job: Job;
  fit_score: number;
  skills_score: number;
  experience_score: number;
  geo_score: number;
  geo_boost_applied: boolean;
  reason: string | null;
}

export interface Resume {
  id: string;
  file_name: string | null;
  parsed_skills: string[];
  experience_years: number | null;
  education: string | null;
  summary: string | null;
  achievements: string[];
  created_at: string;
  updated_at: string;
}

export interface Outreach {
  id: string;
  job_id: string;
  email_subject: string | null;
  email_body: string | null;
  linkedin_msg: string | null;
  cv_bullets: string[];
  status: OutreachStatus;
  sent_at: string | null;
  created_at: string;
}

export interface GmailStatus {
  connected: boolean;
  last_synced_at: string | null;
}

export interface DigestEntry {
  job_id: string;
  title: string;
  company_name: string | null;
  location: string;
  fit_score: number;
  geo_boost_applied: boolean;
  source_url: string | null;
}

export interface DigestPreview {
  subject: string;
  body: string;
  entries: DigestEntry[];
}

export interface IngestionRun {
  id: string;
  source: string;
  status: string;
  fetched_count: number;
  inserted_count: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface EmailSyncRun {
  id: string;
  user_id: string;
  status: string;
  fetched_count: number;
  extracted_count: number;
  inserted_count: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface AdminAnalytics {
  users: { total: number; job_seekers: number; employers: number; pro: number; elite: number };
  jobs: { total: number; active: number; featured: number; aggregated: number };
  applications: { total: number };
  outreach: { total: number; sent: number; success_rate: number | null };
  ingestion_health: { recent_runs_checked: number; success_rate: number | null };
  revenue: { monthly_recurring_estimate_usd: number; pro_subs: number; elite_subs: number };
}

export interface ApiErrorBody {
  detail?: string;
}

export type InterviewStatus = "in_progress" | "completed";

export interface InterviewTurn {
  id: string;
  position: number;
  question: string;
  answer: string | null;
  score: number | null;
  strengths: string[];
  improvements: string[];
  model_answer: string | null;
  answered_at: string | null;
}

export interface InterviewSession {
  id: string;
  job_id: string | null;
  role_title: string;
  company_name: string | null;
  status: InterviewStatus;
  average_score: number | null;
  summary: string | null;
  next_steps: string[];
  created_at: string;
  completed_at: string | null;
  turns: InterviewTurn[];
}

export interface InterviewSessionSummary {
  id: string;
  role_title: string;
  company_name: string | null;
  status: InterviewStatus;
  average_score: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface FunnelStage {
  stage: string;
  label: string;
  count: number;
}

export interface HuntStats {
  funnel: FunnelStage[];
  totals: {
    matches_scored: number;
    applications: number;
    outreach_sent: number;
    interviews_completed: number;
  };
  streak: {
    current_days: number;
    longest_days: number;
    active_days_in_window: number;
    window_days: number;
  };
  conversion: {
    applied_to_interviewing: number | null;
    applied_to_offered: number | null;
  };
  activity: { date: string; active: boolean }[];
}
