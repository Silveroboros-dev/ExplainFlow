"use client";

import React from "react";

type UseAdvancedWorkflowStorageOptions = {
  workflowId: string | null;
  storageKey: string;
  recoverWorkflow: (workflowId: string) => Promise<unknown> | void;
};

export default function useAdvancedWorkflowStorage({
  workflowId,
  storageKey,
  recoverWorkflow,
}: UseAdvancedWorkflowStorageOptions) {
  const recoverWorkflowRef = React.useRef(recoverWorkflow);

  React.useEffect(() => {
    recoverWorkflowRef.current = recoverWorkflow;
  }, [recoverWorkflow]);

  React.useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (workflowId) {
      window.localStorage.setItem(storageKey, workflowId);
    } else {
      window.localStorage.removeItem(storageKey);
    }
  }, [storageKey, workflowId]);

  React.useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const storedWorkflowId = window.localStorage.getItem(storageKey);
    if (!storedWorkflowId || storedWorkflowId === workflowId) {
      return;
    }
    void recoverWorkflowRef.current(storedWorkflowId);
  }, [storageKey, workflowId]);
}
