"use client";

import React from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type DialogMeta = {
  title: string;
  description: string;
  continueLabel?: string | null;
  amendLabel?: string | null;
  amendHelp?: string;
} | null;

type AdvancedActionDialogProps = {
  open: boolean;
  dialogMeta: DialogMeta;
  showAmendHelp: boolean;
  continueDisabled: boolean;
  relaunchDisabled: boolean;
  onOpenChange: (open: boolean) => void;
  onShowAmendHelp: () => void;
  onContinue: () => void;
  onGoBack: () => void;
  onRelaunch: () => void;
};

export default function AdvancedActionDialog({
  open,
  dialogMeta,
  showAmendHelp,
  continueDisabled,
  relaunchDisabled,
  onOpenChange,
  onShowAmendHelp,
  onContinue,
  onGoBack,
  onRelaunch,
}: AdvancedActionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white text-slate-900 border-slate-300">
        <DialogHeader>
          <DialogTitle>{dialogMeta?.title}</DialogTitle>
          <DialogDescription className="text-slate-700">
            {dialogMeta?.description}
          </DialogDescription>
        </DialogHeader>

        {showAmendHelp && dialogMeta?.amendHelp ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
            {dialogMeta.amendHelp}
          </div>
        ) : null}

        <DialogFooter className="gap-2">
          {!showAmendHelp ? (
            <>
              {dialogMeta?.amendLabel ? (
                <Button
                  type="button"
                  variant="outline"
                  className="border-slate-300"
                  onClick={onShowAmendHelp}
                >
                  {dialogMeta.amendLabel}
                </Button>
              ) : null}
              <Button type="button" onClick={onContinue} disabled={continueDisabled}>
                {dialogMeta?.continueLabel ?? "Continue"}
              </Button>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" className="border-slate-300" onClick={onGoBack}>
                Go Back to Amend
              </Button>
              <Button
                type="button"
                onClick={onRelaunch}
                disabled={relaunchDisabled}
              >
                Relaunch Segment
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
