"use client";

import { useEffect, useState } from "react";

import type { SessionSummary } from "@/types/dashboard";

interface SidebarProps {
  sessions: SessionSummary[];
  activeSessionId: number | null;
  isLoading: boolean;
  onSelectSession: (id: number) => void;
  onNewSession: () => void;
}

function formatRelativeTime(isoString: string, now: number): string {
  const timestamp = new Date(isoString).getTime();
  if (Number.isNaN(timestamp)) return "baru saja";
  const diffMs = Math.max(0, now - timestamp);
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 45) return "baru saja";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  const date = new Date(timestamp);
  const today = new Date(now);
  const isYesterday =
    new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() -
      new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() ===
    86400000;
  if (isYesterday) {
    return `Kemarin, ${date.toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} hari lalu`;
  return date.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function Sidebar({
  sessions,
  activeSessionId,
  isLoading,
  onSelectSession,
  onNewSession,
}: SidebarProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const refresh = () => setNow(Date.now());
    const interval = window.setInterval(refresh, 15000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  return (
    <aside className="hidden h-full w-72 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
      <div className="flex items-center justify-between px-4 py-4">
        <h2 className="text-sm font-semibold text-slate-900">Riwayat Riset</h2>
        <button
          type="button"
          onClick={onNewSession}
          className="rounded-md bg-indigo-600 p-1.5 text-white transition-colors hover:bg-indigo-700"
          aria-label="Buat sesi baru"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto px-3 pb-4">
        {isLoading && sessions.length === 0 && (
          <div className="space-y-2">
            <div className="h-16 animate-pulse rounded-lg bg-slate-100" />
            <div className="h-16 animate-pulse rounded-lg bg-slate-100" />
            <div className="h-16 animate-pulse rounded-lg bg-slate-100" />
          </div>
        )}

        {!isLoading && sessions.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-slate-400">
            Belum ada sesi riset. Unggah dokumen atau ajukan pertanyaan untuk memulai.
          </p>
        )}

        {sessions.map((session) => (
          <button
            key={session.id}
            type="button"
            onClick={() => onSelectSession(session.id)}
            className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
              session.id === activeSessionId
                ? "border-indigo-200 bg-indigo-50"
                : "border-transparent hover:bg-slate-50"
            }`}
          >
            <p className="truncate text-sm font-medium text-slate-800">
              {session.title}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {session.source_count} sumber · {formatRelativeTime(session.created_at, now)}
            </p>
          </button>
        ))}
      </div>

      <div className="space-y-2 border-t border-slate-200 px-4 py-4">
        <button
          type="button"
          onClick={() => window.open("/panduan", "_blank", "noopener")}
          className="block text-xs text-slate-500 transition-colors hover:text-slate-700"
        >
          Panduan Penggunaan
        </button>
        <button
          type="button"
          onClick={() => window.open("/hak-privasi", "_blank", "noopener")}
          className="block text-xs text-slate-500 transition-colors hover:text-slate-700"
        >
          Hak &amp; Privasi
        </button>
      </div>
    </aside>
  );
}
