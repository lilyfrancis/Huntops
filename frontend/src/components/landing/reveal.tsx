import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useReveal } from "@/hooks/use-reveal";

interface RevealProps {
  children: ReactNode;
  className?: string;
  delay?: 0 | 1 | 2 | 3 | 4;
  as?: "div" | "section" | "li";
}

const DELAY_CLASS: Record<number, string> = {
  0: "",
  1: "delay-100",
  2: "delay-200",
  3: "delay-300",
  4: "delay-400",
};

export function Reveal({ children, className, delay = 0, as = "div" }: RevealProps) {
  const { ref, isVisible } = useReveal<HTMLDivElement>();
  const Tag = as;
  return (
    <Tag
      ref={ref as never}
      className={cn(
        "translate-y-6 opacity-0 transition-all duration-700 ease-out",
        DELAY_CLASS[delay],
        isVisible && "translate-y-0 opacity-100",
        className,
      )}
    >
      {children}
    </Tag>
  );
}
