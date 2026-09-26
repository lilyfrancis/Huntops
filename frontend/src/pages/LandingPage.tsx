import { LandingNav } from "@/components/landing/landing-nav";
import { Hero } from "@/components/landing/hero";
import { JobMarquee } from "@/components/landing/job-marquee";
import { Features } from "@/components/landing/features";
import { HowItWorks } from "@/components/landing/how-it-works";
import { CreditsChart } from "@/components/landing/credits-chart";
import { Pricing } from "@/components/landing/pricing";
import { FinalCta } from "@/components/landing/final-cta";
import { LandingFooter } from "@/components/landing/landing-footer";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-bg">
      <LandingNav />
      <main>
        <Hero />
        <JobMarquee />
        <Features />
        <HowItWorks />
        <CreditsChart />
        <Pricing />
        <FinalCta />
      </main>
      <LandingFooter />
    </div>
  );
}
