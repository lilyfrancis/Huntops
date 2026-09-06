import { cn } from "@/lib/utils";

/**
 * The wordmark ships in two artwork variants because the mark itself contains
 * navy: recolouring with CSS isn't possible, so `variant` picks the file whose
 * lettering contrasts with the surface it sits on.
 */
export function Logo({
  variant = "navy",
  className,
  height = 32,
}: {
  variant?: "navy" | "white";
  className?: string;
  height?: number;
}) {
  return (
    <img
      src={variant === "navy" ? "/brand/logo-navy.png" : "/brand/logo-white.png"}
      alt="HuntOps"
      height={height}
      style={{ height }}
      className={cn("w-auto select-none", className)}
      draggable={false}
    />
  );
}
