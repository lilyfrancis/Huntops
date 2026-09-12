import { useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/input";

interface TagInputProps {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  max?: number;
  "aria-label": string;
}

/**
 * Free-text chips, for values that can't come from a fixed list.
 *
 * Cities have to be typed rather than picked: the location on a listing is
 * itself free text from whatever board sent it, so there is no canonical list
 * to offer — and no dropdown survives "Downtown Toronto, ON (Hybrid)".
 */
export function TagInput({ value, onChange, placeholder, max = 20, ...rest }: TagInputProps) {
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const name = raw.trim();
    if (!name || value.length >= max) return;
    // Case-insensitive, so "toronto" doesn't sit next to "Toronto".
    if (value.some((v) => v.toLowerCase() === name.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...value, name]);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      // Enter inside a form would submit it; this field is its own thing.
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1.5 rounded-full border border-violet bg-violet-soft px-3 py-1.5 text-sm font-medium text-violet-dark"
            >
              {name}
              <button
                type="button"
                onClick={() => onChange(value.filter((v) => v !== name))}
                aria-label={`Remove ${name}`}
                className="rounded-full p-0.5 transition-colors hover:bg-violet/20"
              >
                <X className="h-3 w-3" strokeWidth={2.5} />
              </button>
            </span>
          ))}
        </div>
      )}
      <Input
        aria-label={rest["aria-label"]}
        value={draft}
        placeholder={value.length >= max ? `Maximum ${max}` : placeholder}
        disabled={value.length >= max}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        /* Committed on blur too — typing a city and clicking Save without
           pressing Enter should not silently discard it. */
        onBlur={() => add(draft)}
      />
    </div>
  );
}
