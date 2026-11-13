"use client";

import { useEffect } from "react";

export function FeedbackToast({ message, tone = "success", onDismiss }: { message: string; tone?: "success" | "error" | "info"; onDismiss?: () => void }) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => onDismiss?.(), 6_000);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;
  return <div className={`feedback-toast feedback-toast-${tone}`} role={tone === "error" ? "alert" : "status"} aria-live={tone === "error" ? "assertive" : "polite"}>
    <span>{message}</span>
    <button type="button" aria-label="Dismiss notification" onClick={onDismiss}>×</button>
  </div>;
}
