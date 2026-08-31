import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";

export function FinalCta() {
  return (
    <section className="relative overflow-hidden py-28">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,_var(--color-accent-soft),_transparent_65%)]"
      />
      <Reveal className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="text-4xl">Ready to let HuntOps hunt?</h2>
        <p className="mt-4 text-ink-muted">
          Free to start. Upgrade whenever you want more reach — no card required to try it.
        </p>
        <div className="mt-8">
          <Button asChild size="lg">
            <Link to="/register">Get started free</Link>
          </Button>
        </div>
      </Reveal>
    </section>
  );
}
