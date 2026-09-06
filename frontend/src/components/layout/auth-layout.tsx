import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { Logo } from "@/components/brand/logo";

const PROMISES = [
  "Six live sources, scored against your CV",
  "Ghost listings flagged before you waste a day",
  "Outreach drafted and sent for you",
];

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel. Navy is the one ground where the bright cyan is legible
          (10.9:1 vs 1.7:1 on white), so the accent work happens here. */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-navy p-10 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            backgroundImage:
              "radial-gradient(circle at 30% 20%, rgba(111,90,251,0.45), transparent 55%), radial-gradient(circle at 80% 75%, rgba(14,219,247,0.28), transparent 50%)",
          }}
        />

        <Link to="/" className="relative w-fit" aria-label="HuntOps home">
          <Logo variant="white" height={28} />
        </Link>

        <div className="relative max-w-md">
          <h1 className="text-4xl leading-tight text-white">
            Your job hunt,
            <br />
            on autopilot.
          </h1>
          <ul className="mt-8 space-y-3">
            {PROMISES.map((p) => (
              <li key={p} className="flex items-start gap-2.5 text-white/80">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-cyan" strokeWidth={2} />
                {p}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative overflow-hidden rounded-xl border border-white/10">
          <img
            src="/brand/hero-dashboard.webp"
            alt=""
            aria-hidden
            loading="lazy"
            className="aspect-[16/7] w-full object-cover object-top opacity-90"
          />
        </div>
      </div>

      <div className="flex items-center justify-center bg-white px-6 py-12">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-8 inline-block lg:hidden" aria-label="HuntOps home">
            <Logo height={28} />
          </Link>
          {children}
        </div>
      </div>
    </div>
  );
}
