import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
export { humanize } from "@/lib/labels";

export interface ChipOption {
  value: string;
  label: string;
}

interface ChipGroupProps {
  options: ChipOption[];
  value: string[];
  onChange: (next: string[]) => void;
  /** Rendered when there is nothing to pick — an empty row of chips reads as a bug. */
  emptyHint?: string;
  disabled?: boolean;
  "aria-label": string;
}

/**
 * A multi-select built from toggle buttons rather than a dropdown.
 *
 * Markets and lanes are short lists where the whole set matters — seeing every
 * option at once is the point, and a closed <select> hides exactly the
 * information ("what can I even pick?") the user needs. Native checkbox
 * semantics via aria-pressed, so keyboard and screen readers get real toggles.
 */
export function ChipGroup({ options, value, onChange, emptyHint, disabled, ...rest }: ChipGroupProps) {
  if (options.length === 0 && emptyHint) {
    return <p className="text-sm text-ink-faint">{emptyHint}</p>;
  }

  const toggle = (option: string) =>
    onChange(value.includes(option) ? value.filter((v) => v !== option) : [...value, option]);

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={rest["aria-label"]}>
      {options.map((option) => {
        const selected = value.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            aria-pressed={selected}
            onClick={() => toggle(option.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50",
              selected
                ? "border-violet bg-violet-soft text-violet-dark"
                : "border-border-strong bg-surface text-ink-muted hover:border-ink-faint hover:text-ink"
            )}
          >
            {selected && <Check className="h-3.5 w-3.5" strokeWidth={2.5} />}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
