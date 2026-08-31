import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <div className="mb-8 flex items-start justify-between gap-4">
      <div>
        {eyebrow && <span className="eyebrow mb-2 block">{eyebrow}</span>}
        <h1 className="text-2xl text-ink">{title}</h1>
        {description && <p className="mt-1.5 max-w-xl text-sm text-ink-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
