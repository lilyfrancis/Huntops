import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";

export function FinalCta() {
  return (
    <section className="px-5 py-24">
      <Reveal className="mx-auto max-w-4xl overflow-hidden rounded-3xl bg-navy px-6 py-16 text-center lift-lg sm:px-12">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10" />
        <h2 className="text-3xl text-white sm:text-4xl">Ready to let HuntOps hunt?</h2>
        <p className="mx-auto mt-4 max-w-lg text-lg text-white/70">
          Pick your role and market, and the engine starts working today. Free to begin —
          no card, no inbox to connect.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link to="/register">
              Start free <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button
            asChild
            size="lg"
            variant="outline"
            className="border-white/25 bg-transparent text-white hover:border-white hover:text-white"
          >
            <Link to="/login">Sign in</Link>
          </Button>
        </div>
      </Reveal>
    </section>
  );
}
