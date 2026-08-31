import { useEffect, useState } from "react";
import { useReveal } from "@/hooks/use-reveal";

interface CounterProps {
  to: number;
  suffix?: string;
  prefix?: string;
  durationMs?: number;
}

export function Counter({ to, suffix = "", prefix = "", durationMs = 1200 }: CounterProps) {
  const { ref, isVisible } = useReveal<HTMLSpanElement>(0.6);
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!isVisible) return;
    let frame: number;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / durationMs, 1);
      const eased = 1 - (1 - progress) * (1 - progress);
      setValue(Math.round(to * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [isVisible, to, durationMs]);

  return (
    <span ref={ref}>
      {prefix}
      {value}
      {suffix}
    </span>
  );
}
