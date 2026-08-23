import React from "react";
import type { LucideIcon } from "lucide-react";

interface Props {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
}

export function SectionHeader({ icon: Icon, title, subtitle }: Props) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="size-10 rounded-xl bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
        <Icon className="h-5 w-5 text-teal-600 dark:text-teal-400" />
      </div>
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {subtitle && (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
