"use client";

import React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

type ChatRole = "agent" | "user" | "system";

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
};

type PendingAssistantAction = {
  title: string;
  message: string;
  confirmLabel: string;
};

type AdvancedAssistantPanelProps = {
  chatMessages: ChatMessage[];
  chatInput: string;
  isWorking: boolean;
  pendingAction: PendingAssistantAction | null;
  pendingActionDisabled: boolean;
  primaryActionClassName: string;
  primaryActionLabelClassName: string;
  chatScrollAnchorRef: React.RefObject<HTMLDivElement | null>;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onChatInputChange: (value: string) => void;
  onConfirmPendingAction: () => void;
  onDismissPendingAction: () => void;
};

const chatRoleMeta = (role: ChatRole): {
  rowClassName: string;
  bubbleClassName: string;
  label: string;
} => {
  if (role === "user") {
    return {
      rowClassName: "justify-end",
      bubbleClassName: "border-blue-300 bg-blue-50 text-blue-950",
      label: "You",
    };
  }
  if (role === "system") {
    return {
      rowClassName: "justify-center",
      bubbleClassName: "border-slate-300 bg-slate-100 text-slate-700",
      label: "System",
    };
  }
  return {
    rowClassName: "justify-start",
    bubbleClassName: "border-slate-200 bg-white text-slate-900",
    label: "ExplainFlow",
  };
};

export default function AdvancedAssistantPanel({
  chatMessages,
  chatInput,
  isWorking,
  pendingAction,
  pendingActionDisabled,
  primaryActionClassName,
  primaryActionLabelClassName,
  chatScrollAnchorRef,
  onSubmit,
  onChatInputChange,
  onConfirmPendingAction,
  onDismissPendingAction,
}: AdvancedAssistantPanelProps) {
  return (
    <Card className="bg-white/95 text-slate-900 backdrop-blur-xl shadow-[0_20px_40px_rgba(15,23,42,0.08)] border-slate-300/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-slate-900">ExplainFlow Assistant</CardTitle>
        <CardDescription className="text-slate-600">
          Latest exchange with the workflow assistant. Detailed execution stays in Agent Session Notes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-[22px] border border-slate-200 bg-slate-50/80 p-3">
          <div className="mb-2 flex items-center justify-between gap-3 px-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Latest Exchange</p>
            <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
              Live
            </span>
          </div>
          <ScrollArea className="h-[180px] rounded-[18px] border border-slate-200 bg-white p-3 shadow-[0_8px_18px_rgba(15,23,42,0.03)] md:h-[210px]">
            <div className="space-y-3 pr-2">
              {chatMessages.map((message) => {
                const meta = chatRoleMeta(message.role);
                return (
                  <div key={message.id} className={`flex w-full items-start gap-2 ${meta.rowClassName}`}>
                    <div className={`max-w-[90%] rounded-2xl border px-3 py-2 text-sm leading-6 shadow-sm ${meta.bubbleClassName}`}>
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide opacity-70">{meta.label}</p>
                      <p className="whitespace-pre-wrap">{message.text}</p>
                    </div>
                  </div>
                );
              })}
              {isWorking ? (
                <div className="flex w-full items-start gap-2 justify-start">
                  <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-600">ExplainFlow</p>
                    <Skeleton className="h-3 w-28 bg-slate-200" />
                    <Skeleton className="mt-2 h-3 w-44 bg-slate-200" />
                    <Skeleton className="mt-2 h-3 w-36 bg-slate-200" />
                  </div>
                </div>
              ) : null}
              <div ref={chatScrollAnchorRef} />
            </div>
          </ScrollArea>
        </div>
        {pendingAction ? (
          <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-800">
                Awaiting Confirmation
              </p>
              <p className="text-sm font-semibold text-amber-950">{pendingAction.title}</p>
              <p className="text-sm leading-6 text-amber-950">{pendingAction.message}</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" className="border-amber-300" onClick={onDismissPendingAction}>
                Not Now
              </Button>
              <Button type="button" onClick={onConfirmPendingAction} disabled={pendingActionDisabled}>
                {pendingAction.confirmLabel}
              </Button>
            </div>
          </div>
        ) : null}
        <form onSubmit={onSubmit} className="space-y-3 rounded-[22px] border border-slate-200 bg-slate-50/80 p-3">
          <Textarea
            value={chatInput}
            onChange={(event) => onChatInputChange(event.target.value)}
            placeholder='Ask naturally, e.g. "What should I do next?" or "Open render profile."'
            className="min-h-[84px] resize-none bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
          />
          <div className="rounded-[24px] border border-slate-200 bg-white/90 p-3 shadow-[0_8px_18px_rgba(15,23,42,0.03)]">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1 px-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Assistant request
                </p>
                <p className="text-sm text-slate-700">Use the assistant to explain state, move the workflow, or suggest the next action.</p>
              </div>
              <Button
                type="submit"
                className={`${primaryActionClassName} sm:min-w-[240px]`}
              >
                <span className="space-y-1 text-left">
                  <span className={primaryActionLabelClassName}>
                    Assistant
                  </span>
                  <span className="block text-base font-semibold">Send Request</span>
                </span>
              </Button>
            </div>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
