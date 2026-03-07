"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export type AgentNoteType = "info" | "checkpoint" | "qa" | "trace" | "error";

export type AgentNote = {
  id: string;
  type: AgentNoteType;
  stage: string;
  message: string;
  timestamp: number;
};

type AgentActivityPanelProps = {
  title?: string;
  subtitle?: string;
  notes: AgentNote[];
  currentStatus?: string;
  className?: string;
  notesHeightClassName?: string;
};

const typeBadgeClass: Record<AgentNoteType, string> = {
  info: "bg-slate-100 text-slate-800 border-slate-200",
  checkpoint: "bg-blue-100 text-blue-800 border-blue-200",
  qa: "bg-amber-100 text-amber-900 border-amber-200",
  trace: "bg-indigo-100 text-indigo-900 border-indigo-200",
  error: "bg-rose-100 text-rose-900 border-rose-200",
};

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

function formatTime(ts: number): string {
  return timeFormatter.format(new Date(ts));
}

export default function AgentActivityPanel({
  title = "Agent Activity",
  subtitle = "Live progress notes from the orchestration loop.",
  notes,
  currentStatus = "",
  className,
  notesHeightClassName,
}: AgentActivityPanelProps) {
  const latestNote = notes[0];

  return (
    <Card className={cn("bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-slate-900">{title}</CardTitle>
          {latestNote ? (
            <Badge variant="secondary" className={typeBadgeClass[latestNote.type]}>
              {latestNote.type.toUpperCase()}
            </Badge>
          ) : null}
        </div>
        <CardDescription className="text-slate-600">{subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {currentStatus ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {currentStatus}
          </div>
        ) : null}
        <ScrollArea className={cn("h-52 pr-3", notesHeightClassName)}>
          <div className="space-y-2">
            {notes.length === 0 ? (
              <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-sm text-slate-500">
                Agent notes will appear here as checkpoints, QA decisions, and traceability results stream in.
              </div>
            ) : (
              notes.map((note) => (
                <div
                  key={note.id}
                  className="rounded-md border border-slate-200 bg-white px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {note.stage}
                    </p>
                    <p className="text-xs text-slate-400">{formatTime(note.timestamp)}</p>
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{note.message}</p>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
