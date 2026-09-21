import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";

export function FinalCta() {
  return (
    <section className="shell py-24 lg:py-32">
      <Reveal className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-navy px-6 py-20 text-center lift-lg sm:px-12 lg:py-24 grain">
        {/* The same aurora as the hero, so the page closes on the note it
            opened with rather than on a flat navy slab. */}
        <div
          aria-hidden
          className="animate-drift-a pointer-events-none absolute -left-24 top-[-30%] -z-10 h-[26rem] w-[26rem] rounded-full bg-violet/35 blur-[90px]"
        />
        <div
          aria-hidden
          className="animate-drift-b pointer-events-none absolute -right-20 bottom-[-40%] -z-10 h-[24rem] w-[24rem] rounded-full bg-cyan/20 blur-[100px]"
        />
        <h2 className="t-h2 text-white">Your next application, without the form</h2>
        <p className="t-lead mx-auto mt-5 max-w-xl text-white/70">
          Tell us the role and the market. Your first one is on us — no card, and
          nothing to install.
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
