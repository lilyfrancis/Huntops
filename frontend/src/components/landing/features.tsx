import {
  Radar,
  Target,
  MailCheck,
  Send,
  MessageSquare,
  Newspaper,
  ShieldCheck,
} from "lucide-react";
import { Reveal } from "@/components/landing/reveal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const FEATURES = [
  {
    icon: Radar,
    tone: "text-accent",
    title: "Real job aggregation",
    body: "Six live sources, deduped and refreshed daily — not a stale scrape from last week.",
  },
  {
    icon: Target,
    tone: "text-cyan",
    title: "AI fit scoring",
    body: "Every job is scored against your résumé by Claude, with a location-aware boost so nearby roles surface first.",
  },
  {
    icon: MailCheck,
    tone: "text-good",
    title: "Email-alert bridge",
    body: "Connect Gmail once. Job alerts already landing in your inbox get auto-labeled and extracted into your feed.",
  },
  {
    icon: Send,
    tone: "text-accent",
    title: "Autopilot Outreach",
    body: "Elite finds the hiring recruiter via Apollo, drafts a pitch with AI, and sends it from your own Gmail — no copy-paste.",
  },
  {
    icon: MessageSquare,
    tone: "text-cyan",
    title: "Mock interview simulator",
    body: "Practise the real screen for the role you're chasing, with every answer scored and rewritten stronger.",
  },
  {
    icon: Newspaper,
    tone: "text-good",
    title: "Daily digest",
    body: "One email each morning with your best new matches, so you never have to go looking.",
  },
  {
    icon: ShieldCheck,
    tone: "text-good",
    title: "Built for both sides",
    body: "Employers post and manage listings; admins moderate every job and account before it goes live.",
  },
];

export function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-6 py-28">
      <Reveal className="mx-auto max-w-2xl text-center">
        <span className="eyebrow">What HuntOps does</span>
        <h2 className="mt-3 text-4xl">Everything a job hunt needs, running on autopilot</h2>
      </Reveal>

      <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, i) => (
          <Reveal key={feature.title} delay={(i % 3) as 0 | 1 | 2}>
            <Card className="h-full transition-colors hover:border-border-strong">
              <CardHeader>
                <feature.icon className={`h-6 w-6 ${feature.tone}`} strokeWidth={1.75} />
                <CardTitle className="mt-3 text-lg">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-ink-muted">{feature.body}</p>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
