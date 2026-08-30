"use client";

import type { ToastItem } from "@/types/dashboard";

interface ToastHostProps {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}

const toastStyles: Record<ToastItem["type"], { wrap: string; icon: string; iconClass: string }> = {
  success: {
    wrap: "border-emerald-200 bg-emerald-50",
    icon: "M5 13l4 4L19 7",
    iconClass: "text-emerald-600",
  },
  error: {
    wrap: "border-rose-200 bg-rose-50",
    icon: "M6 18L18 6M6 6l12 12",
    iconClass: "text-rose-600",
  },
  info: {
    wrap: "border-slate-200 bg-white",
    icon: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    iconClass: "text-slate-500",
  },
};

export default function ToastHost({ toasts, onDismiss }: ToastHostProps) {
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => {
        const style = toastStyles[toast.type];
        return (
          <button
            key={toast.id}
            type="button"
            onClick={() => onDismiss(toast.id)}
            className={`pointer-events-auto flex items-start gap-3 rounded-lg border p-3 text-left shadow-lg ${style.wrap}`}
          >
            <svg
              className={`mt-0.5 h-5 w-5 shrink-0 ${style.iconClass}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d={style.icon} />
            </svg>
            <span className="text-sm text-slate-700">{toast.message}</span>
          </button>
        );
      })}
    </div>
  );
}
