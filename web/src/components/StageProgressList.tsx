"use client";

import React from "react";
import { AlertCircle, Check, Circle, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { StageProgressItem, StageProgressStatus } from "@/lib/advanced";

type StageProgressListProps = {
  title?: string;
  subtitle?: string;
  items: StageProgressItem[];
  className?: string;
};

const statusMeta: Record<StageProgressStatus, {
  wrapperClassName: string;
  iconClassName: string;
  textClassName: string;
  Icon: React.ComponentType<{ className?: string }>;
}> = {
  pending: {
    wrapperClassName: "border-slate-200 bg-white",
    iconClassName: "border-slate-300 text-slate-400",
    textClassName: "text-slate-600",
    Icon: Circle,
  },
  active: {
    wrapperClassName: "border-sky-200/80 bg-sky-50/80",
    iconClassName: "border-sky-300 text-sky-600",
    textClassName: "text-sky-950",
    Icon: Loader2,
  },
  done: {
    wrapperClassName: "border-emerald-200/80 bg-emerald-50/70",
    iconClassName: "border-emerald-300 bg-emerald-500 text-white",
    textClassName: "text-slate-800",
    Icon: Check,
  },
  error: {
    wrapperClassName: "border-rose-200 bg-rose-50",
    iconClassName: "border-rose-300 text-rose-600",
    textClassName: "text-rose-900",
    Icon: AlertCircle,
  },
};

export default function StageProgressList({
  title = "Under the Hood",
  subtitle,
  items,
  className,
}: StageProgressListProps) {
  return (
    <div className={cn("space-y-3 rounded-[22px] border border-slate-200 bg-white p-3.5 shadow-[0_8px_18px_rgba(15,23,42,0.03)]", className)}>
      <div className="space-y-1">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</p>
        {subtitle ? <p className="text-[13px] leading-5 text-slate-600">{subtitle}</p> : null}
      </div>
      <div className="space-y-2">
        {items.map((item) => {
          const meta = statusMeta[item.status];
          const Icon = meta.Icon;
          return (
            <div
              key={item.id}
              className={cn("flex items-start gap-3 rounded-[18px] border px-3 py-3", meta.wrapperClassName)}
            >
              <span className={cn("mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full border", meta.iconClassName)}>
                <Icon className={cn("h-4 w-4", item.status === "active" ? "animate-spin" : "")} />
              </span>
              <div className="min-w-0 space-y-1">
                <p className={cn("text-sm font-medium", meta.textClassName)}>{item.label}</p>
                {item.detail ? <p className="text-[12px] leading-5 text-slate-500">{item.detail}</p> : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
