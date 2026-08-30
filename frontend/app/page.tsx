"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ChatSection from "@/components/ChatSection";
import DocumentPanel from "@/components/DocumentPanel";
import ExportPanel, { type ExportFormat } from "@/components/ExportPanel";
import Sidebar from "@/components/Sidebar";
import ToastHost from "@/components/ToastHost";
import UploadSection from "@/components/UploadSection";
import { apiClient } from "@/lib/api/client";
import type {
  ChatMessage,
  DeleteDocumentResponse,
  FileIngestItem,
  MultiIngestResponse,
  SessionDetail,
  SessionDocument,
  SessionSummary,
  ToastItem,
} from "@/types/dashboard";

export default function DashboardPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [activeDocuments, setActiveDocuments] = useState<SessionDocument[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSessionsLoading, setIsSessionsLoading] = useState(true);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const messageIdRef = useRef(0);
  const toastIdRef = useRef(0);
  const knownSessionIdsRef = useRef<Set<number>>(new Set());

  const nextMessageId = useCallback(() => {
    messageIdRef.current += 1;
    return messageIdRef.current;
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (type: ToastItem["type"], message: string) => {
      toastIdRef.current += 1;
      const id = toastIdRef.current;
      setToasts((previous) => [...previous, { id, type, message }]);
      window.setTimeout(() => dismissToast(id), 4000);
    },
    [dismissToast],
  );

  const refreshSessions = useCallback(async () => {
    const knownIds = knownSessionIdsRef.current;
    if (knownIds.size === 0) {
      setSessions([]);
      return;
    }
    try {
      const sessionList = await apiClient.get<SessionSummary[]>("/sessions");
      setSessions(sessionList.filter((session) => knownIds.has(session.id)));
    } catch {
      showToast("error", "Gagal memuat daftar sesi.");
    }
  }, [showToast]);

  const registerSessionId = useCallback((sessionId: number) => {
    knownSessionIdsRef.current.add(sessionId);
  }, []);

  const loadSessionDetail = useCallback(
    async (sessionId: number) => {
      try {
        const detail = await apiClient.get<SessionDetail>(`/sessions/${sessionId}`);
        const historicalMessages: ChatMessage[] = [...detail.messages]
          .reverse()
          .flatMap((entry) => [
            { id: nextMessageId(), role: "user", content: entry.prompt } as ChatMessage,
            {
              id: nextMessageId(),
              role: "assistant",
              content: entry.generated_response,
              citations: entry.citations,
            } as ChatMessage,
          ]);
        setMessages(historicalMessages);
        setActiveDocuments(detail.documents);
        setActiveSessionId(sessionId);
      } catch {
        showToast("error", "Gagal memuat obrolan sesi.");
      }
    },
    [nextMessageId, showToast],
  );

  const reloadActiveSession = useCallback(async () => {
    if (activeSessionId === null) return;
    try {
      const detail = await apiClient.get<SessionDetail>(`/sessions/${activeSessionId}`);
      setActiveDocuments(detail.documents);
    } catch {
      // silent - session list refresh still informs the user
    }
  }, [activeSessionId]);

  useEffect(() => {
    // Trial mode: start with an empty session list on every page load.
    // Old sessions remain stored in the backend unless deleted manually, but
    // they are not auto-loaded into the sidebar.
    setIsSessionsLoading(false);
  }, []);

  const handleNewSession = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setActiveDocuments([]);
  }, []);

  const handleSelectSession = useCallback(
    (sessionId: number) => {
      loadSessionDetail(sessionId);
    },
    [loadSessionDetail],
  );

  const handleFilesUpload = useCallback(
    async (
      files: File[],
      onProgress?: (percent: number) => void,
    ): Promise<FileIngestItem[]> => {
      if (files.length === 0) return [];
      setIsUploading(true);
      try {
        const response = await apiClient.uploadFilesWithProgress<MultiIngestResponse>(
          "/ingest/files",
          files,
          activeSessionId ?? undefined,
          (percent) => onProgress?.(percent),
        );
        onProgress?.(100);
        const succeeded = response.files.filter((file) => file.success).length;
        // Only switch to / register the session when at least one file actually
        // succeeded and the backend returned a valid session id. A fully-rejected
        // batch must not create an empty session entry in the sidebar/history.
        if (succeeded > 0 && response.session_id > 0) {
          setActiveSessionId(response.session_id);
          registerSessionId(response.session_id);
          await refreshSessions();
          await loadSessionDetail(response.session_id);
        }
        showToast(
          succeeded === response.files.length ? "success" : "info",
          `${succeeded} dari ${response.files.length} file berhasil diindeks ke sesi.`,
        );
        return response.files;
      } catch (error) {
        showToast(
          "error",
          error instanceof Error ? error.message : "Gagal mengunggah dokumen.",
        );
        return [];
      } finally {
        setIsUploading(false);
      }
    },
    [activeSessionId, registerSessionId, refreshSessions, loadSessionDetail, showToast],
  );

  const handleUrlUpload = useCallback(
    async (url: string): Promise<boolean> => {
      setIsUploading(true);
      try {
        const response = await apiClient.post<{ session_id: number; message: string }>(
          "/ingest/url",
          { url, session_id: activeSessionId ?? null },
        );
        setActiveSessionId(response.session_id);
        registerSessionId(response.session_id);
        await refreshSessions();
        await loadSessionDetail(response.session_id);
        showToast("success", response.message);
        return true;
      } catch (error) {
        showToast(
          "error",
          error instanceof Error ? error.message : "Gagal mengunggah tautan.",
        );
        return false;
      } finally {
        setIsUploading(false);
      }
    },
    [activeSessionId, registerSessionId, refreshSessions, loadSessionDetail, showToast],
  );

  const handleDeleteDocument = useCallback(
    async (document: SessionDocument): Promise<boolean> => {
      if (activeSessionId === null || deletingId !== null) return false;
      setDeletingId(document.id);
      try {
        const response = await apiClient.del<DeleteDocumentResponse>(
          `/sessions/${activeSessionId}/documents/${document.id}`,
        );
        showToast("success", `Dokumen dihapus (${response.documents_removed} bagian).`);
        await refreshSessions();
        await reloadActiveSession();
        return true;
      } catch (error) {
        showToast(
          "error",
          error instanceof Error ? error.message : "Gagal menghapus dokumen.",
        );
        return false;
      } finally {
        setDeletingId(null);
      }
    },
    [activeSessionId, deletingId, reloadActiveSession, refreshSessions, showToast],
  );

  const handleDeleteUploadedFile = useCallback(
    async (documentId: number): Promise<boolean> => {
      return handleDeleteDocument({ id: documentId } as SessionDocument);
    },
    [handleDeleteDocument],
  );

  const handleSendQuery = useCallback(
    async (query: string) => {
      const userMessage: ChatMessage = {
        id: nextMessageId(),
        role: "user",
        content: query,
      };
      setMessages((previous) => [...previous, userMessage]);
      setIsChatLoading(true);

      try {
        const response = await apiClient.post<{
          session_id: number;
          generated_response: string;
          citations: ChatMessage["citations"];
          include_citations: boolean;
        }>("/chat/query", { query, session_id: activeSessionId ?? null });

        setActiveSessionId(response.session_id);
        registerSessionId(response.session_id);
        setMessages((previous) => [
          ...previous,
          {
            id: nextMessageId(),
            role: "assistant",
            content: response.generated_response,
            citations: response.citations,
            includeCitations: response.include_citations,
          },
        ]);
        await refreshSessions();
      } catch (error) {
        showToast(
          "error",
          error instanceof Error ? error.message : "Gagal memproses pertanyaan.",
        );
      } finally {
        setIsChatLoading(false);
      }
    },
    [activeSessionId, registerSessionId, nextMessageId, refreshSessions, showToast],
  );

  const handleExport = useCallback(
    async (format: ExportFormat) => {
      if (activeSessionId === null) {
        showToast("info", "Unggah dokumen terlebih dahulu untuk dapat melakukan ekspor.");
        return;
      }
      setIsExporting(true);
      try {
        const { blob, filename } = await apiClient.downloadFile(
          `/export/${activeSessionId}?format=${format}`,
        );
        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(objectUrl);
        showToast("success", "Ekspor berhasil diunduh.");
      } catch (error) {
        showToast(
          "error",
          error instanceof Error ? error.message : "Gagal mengekspor hasil.",
        );
      } finally {
        setIsExporting(false);
      }
    },
    [activeSessionId, showToast],
  );

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-50">
      {/* Mobile top bar */}
      <div className="z-40 shrink-0 border-b border-slate-200 bg-white/95 backdrop-blur lg:hidden">
        <div className="flex items-center gap-2 px-4 py-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            AI
          </span>
          <select
            value={activeSessionId ?? ""}
            onChange={(event) => {
              const value = event.target.value;
              if (value) handleSelectSession(Number(value));
              else handleNewSession();
            }}
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-700 outline-none focus:border-indigo-500"
          >
            <option value="">Buat sesi baru…</option>
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleNewSession}
            className="shrink-0 rounded-md bg-indigo-600 p-2 text-white"
            aria-label="Buat sesi baru"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          isLoading={isSessionsLoading}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
        />

        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:py-8">
          <header className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900">
              AI Research &amp; Knowledge Synthesis Agent
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Kelola sumber, ajukan pertanyaan, dan ekspor hasil riset Anda. Unggah banyak
              file sekaligus dalam satu sesi untuk dibahas secara kolektif.
            </p>
          </header>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-1">
              <UploadSection
                isUploading={isUploading}
                onFilesUpload={handleFilesUpload}
                onUrlUpload={handleUrlUpload}
                onDeleteUploadedFile={handleDeleteUploadedFile}
              />
              <DocumentPanel
                documents={activeDocuments}
                onDelete={handleDeleteDocument}
                deletingId={deletingId}
              />
              <ExportPanel isExporting={isExporting} onExport={handleExport} />
            </div>

            <div className="flex min-h-[32rem] flex-col lg:col-span-2 lg:h-full">
              <ChatSection
                messages={messages}
                isLoading={isChatLoading}
                onSendQuery={handleSendQuery}
              />
            </div>
          </div>
        </main>
      </div>

      {/* Footer with marquee */}
      <footer className="shrink-0 border-t border-slate-200 bg-white">
        <div className="overflow-hidden whitespace-nowrap py-3">
          <span className="inline-block animate-marquee pr-12 text-sm font-medium text-indigo-600">
            Support Document PDF, DOCX, PPT, TXT, dan URL&nbsp;&nbsp;✦
          </span>
        </div>
        <div className="py-3">
          <p className="text-center text-xs text-slate-400">
            AI Research &amp; Knowledge Synthesis Agent, © 2026
          </p>
        </div>
      </footer>

      <ToastHost toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

