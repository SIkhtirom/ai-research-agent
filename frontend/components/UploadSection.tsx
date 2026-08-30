"use client";

import { useRef, useState } from "react";

import type { FileIngestItem } from "@/types/dashboard";

interface UploadSectionProps {
  isUploading: boolean;
  onFilesUpload: (
    files: File[],
    onProgress?: (percent: number) => void,
  ) => Promise<FileIngestItem[]>;
  onUrlUpload: (url: string) => Promise<boolean>;
  onDeleteUploadedFile?: (documentId: number) => Promise<boolean>;
}

type FileStatus = "uploading" | "success" | "error";

interface UploadedFileEntry {
  id: number;
  name: string;
  status: FileStatus;
  reason?: string;
  documentId?: number;
  isDeleting?: boolean;
}

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
];

const acceptedFileTypes = [...ACCEPTED_EXTENSIONS, ...ACCEPTED_MIME_TYPES].join(",");

const maxFileSize = 10 * 1024 * 1024;

// Explicit, PPTX-inclusive UI validation. The check is case-insensitive on both
// the extension and the MIME type, so ".PPTX"/".Pptx"/"Demo.pptx" all pass. A
// file is accepted if EITHER its extension OR its MIME type is recognised, so a
// PowerPoint keeps the extension as the authoritative signal even when the
// browser reports an empty/generic MIME type. Debug logs are left in on purpose
// so a rejected/ignored file can be traced in the browser console (F12).
const isAcceptedFile = (file: File): boolean => {
  const rawName = file.name ?? "";
  const lowerName = rawName.toLowerCase();
  const dotIndex = lowerName.lastIndexOf(".");
  // Normalise to ".ext" (lowercase). No dot -> empty string (not accepted by
  // extension alone), not a single stray character.
  const extension = dotIndex >= 0 ? lowerName.slice(dotIndex) : "";
  const mime = (file.type ?? "").toLowerCase();
  const accepted =
    ACCEPTED_EXTENSIONS.includes(extension) || ACCEPTED_MIME_TYPES.includes(mime);
  console.log("[Upload] isAcceptedFile:", {
    rawName,
    lowerName,
    extension,
    mime,
    accepted,
    supportedExtensions: ACCEPTED_EXTENSIONS,
    supportedMime: ACCEPTED_MIME_TYPES,
  });
  if (!accepted) {
    console.log("[Upload] File REJECTED by isAcceptedFile:", { rawName, extension, mime });
  }
  return accepted;
};

export default function UploadSection({
  isUploading,
  onFilesUpload,
  onUrlUpload,
  onDeleteUploadedFile,
}: UploadSectionProps) {
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [files, setFiles] = useState<UploadedFileEntry[]>([]);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileIdRef = useRef(0);

  const updateFile = (id: number, status: FileStatus) => {
    setFiles((previous) =>
      previous.map((entry) => (entry.id === id ? { ...entry, status } : entry)),
    );
  };

  const setEntryDocumentId = (id: number, documentId: number) => {
    setFiles((previous) =>
      previous.map((entry) => (entry.id === id ? { ...entry, documentId } : entry)),
    );
  };

  const setEntryDeleting = (id: number, isDeleting: boolean) => {
    setFiles((previous) =>
      previous.map((entry) => (entry.id === id ? { ...entry, isDeleting } : entry)),
    );
  };

  const removeUploadedEntry = (id: number) => {
    setFiles((previous) => previous.filter((entry) => entry.id !== id));
  };

  const handleDeleteUploaded = async (entry: UploadedFileEntry) => {
    if (!entry.documentId || !onDeleteUploadedFile || entry.isDeleting) return;
    setEntryDeleting(entry.id, true);
    try {
      const deleted = await onDeleteUploadedFile(entry.documentId);
      if (deleted) removeUploadedEntry(entry.id);
    } finally {
      setEntryDeleting(entry.id, false);
    }
  };

  const handleBatchUpload = async (selectedFiles: File[]) => {
    setUploadError(null);
    // Build the queue entries. Files over the size limit are added immediately
    // with a clear failure reason (never silently dropped), unsupported files are
    // marked as failed, and supported/under-limit files are uploaded.
    const entries: UploadedFileEntry[] = selectedFiles.map((file) => {
      fileIdRef.current += 1;
      if (file.size > maxFileSize) {
        return {
          id: fileIdRef.current,
          name: file.name,
          status: "error",
          reason: `File Upload melebihi dari 10MB: ${file.name}`,
        };
      }
      const accepted = isAcceptedFile(file);
      return {
        id: fileIdRef.current,
        name: file.name,
        status: accepted ? "uploading" : "error",
      };
    });
    const oversizedFiles = selectedFiles.filter((file) => file.size > maxFileSize);
    if (oversizedFiles.length > 0) {
      console.log(
        "[Upload] Rejected oversized files:",
        oversizedFiles.map((f) => ({
          name: f.name,
          size: f.size,
          max: maxFileSize,
          sizeMB: (f.size / (1024 * 1024)).toFixed(2),
        })),
      );
      // Show the limit error clearly on the UI (pop-up-style banner).
      setUploadError(
        oversizedFiles
          .map((file) => `File Upload melebihi dari 10MB: ${file.name}`)
          .join("\n"),
      );
    }

    setFiles((previous) => [...previous, ...entries]);
    console.log("[Upload] Enqueued entries:", entries);

    // Only files that are supported AND within the size limit are uploaded.
    const uploadableFiles = selectedFiles.filter(
      (file) => file.size <= maxFileSize && isAcceptedFile(file),
    );

    setUploadPercent(0);
    let results: FileIngestItem[] = [];
    if (uploadableFiles.length > 0) {
      try {
        results = await onFilesUpload(uploadableFiles, (percent) =>
          setUploadPercent(percent),
        );
      } catch (error) {
        console.error("[Upload] onFilesUpload threw:", {
          uploadableFiles: uploadableFiles.map((f) => ({
            name: f.name,
            type: f.type,
            size: f.size,
          })),
          error: error instanceof Error ? error.message : error,
        });
        setUploadPercent(null);
        // Mark everything still "uploading" as failed so the queue is consistent.
        uploadableFiles.forEach((file) => {
          const entry = entries.find((e) => e.name === file.name);
          if (entry) updateFile(entry.id, "error");
        });
        return;
      }
    }
    const byName = new Map<string, FileIngestItem>();
    if (results) {
      results.forEach((item: FileIngestItem) => byName.set(item.filename, item));
    }

    entries.forEach((entry) => {
      const item = byName.get(entry.name);
      if (!item) {
        // The backend did not report this file (e.g. it was rejected locally or
        // the whole request failed). Never mark it as successfully uploaded.
        console.log("[Upload] No backend item for file:", entry.name);
        updateFile(entry.id, "error");
        return;
      }
      if (item.document_ids && item.document_ids.length > 0) {
        setEntryDocumentId(entry.id, Number(item.document_ids[0]));
      }
      updateFile(entry.id, item.success ? "success" : "error");
    });
    setUploadPercent(null);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDraggingOver(false);
    const droppedFiles = Array.from(event.dataTransfer.files);
    console.log(
      "[Upload] handleDrop:",
      droppedFiles.map((f) => ({ name: f.name, type: f.type, size: f.size })),
    );
    if (droppedFiles.length) handleBatchUpload(droppedFiles);
  };

  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    console.log(
      "[Upload] handleFileSelection:",
      selectedFiles.map((f) => ({ name: f.name, type: f.type, size: f.size })),
    );
    if (selectedFiles.length) handleBatchUpload(selectedFiles);
    event.target.value = "";
  };

  const handleUrlSubmission = async () => {
    const trimmedUrl = urlInput.trim();
    if (!trimmedUrl || isUploading) return;
    setUrlInput("");
    await onUrlUpload(trimmedUrl);
  };

  const showUploadingFeedback = files.some((entry) => entry.status === "uploading");

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">Unggah Dokumen</h3>
      <p className="mt-1 text-sm text-slate-500">
        Seret beberapa file sekaligus atau tempelkan tautan. Semua diindeks ke dalam
        satu sesi sehingga bisa dibahas secara kolektif.
      </p>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setIsDraggingOver(true);
        }}
        onDragLeave={() => setIsDraggingOver(false)}
        onDrop={handleDrop}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          isDraggingOver
            ? "border-indigo-500 bg-indigo-50"
            : "border-slate-300 hover:border-indigo-400 hover:bg-slate-50"
        }`}
      >
        <svg
          className="mb-3 h-10 w-10 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.4-1.5 3 3 0 012.2 5.475A4.5 4.5 0 0117.25 19.5H6.75z"
          />
        </svg>
        <p className="text-sm font-medium text-slate-700">
          Seret &amp; jatuhkan file di sini
        </p>
        <p className="mt-1 text-xs text-slate-400">
          PDF, DOCX, PPTX, atau TXT · maks. 10MB per file
        </p>
        <label className="mt-4 inline-block cursor-pointer rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700">
          {showUploadingFeedback ? "Mengunggah…" : "Pilih File"}
          <input
            type="file"
            multiple
            accept={acceptedFileTypes}
            className="hidden"
            onChange={handleFileSelection}
          />
        </label>
      </div>

      {uploadError && (
        <div
          role="alert"
          className="mt-4 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          <svg
            className="mt-0.5 h-5 w-5 shrink-0 text-rose-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v4m0 4h.01M10.29 3.86l-8.09 14A2 2 0 003.93 21h16.14a2 2 0 001.73-3L13.71 3.86a2 2 0 00-3.42 0z"
            />
          </svg>
          <div className="min-w-0 flex-1 whitespace-pre-line">{uploadError}</div>
          <button
            type="button"
            onClick={() => setUploadError(null)}
            aria-label="Tutup notifikasi"
            className="shrink-0 rounded-md p-1 text-rose-400 transition-colors hover:bg-rose-100 hover:text-rose-700"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {uploadPercent !== null && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Mengunggah…</span>
            <span>{uploadPercent}%</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-indigo-500 transition-[width] duration-200"
              style={{ width: `${uploadPercent}%` }}
            />
          </div>
        </div>
      )}

      {files.length > 0 && (
        <ul className="scrollbar-hide mt-4 max-h-40 space-y-2 overflow-y-auto pr-1">
          {files.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            >
              {entry.status === "uploading" ? (
                <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
              ) : entry.status === "success" ? (
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white">
                  ✓
                </span>
              ) : (
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white">
                  ✕
                </span>
              )}
              <span
                className="min-w-0 flex-1 truncate text-slate-700"
                title={entry.reason ?? entry.name}
              >
                {entry.name}
              </span>
              {entry.status === "success" && (
                <button
                  type="button"
                  onClick={() => handleDeleteUploaded(entry)}
                  disabled={entry.isDeleting || !entry.documentId}
                  aria-label={`Hapus ${entry.name}`}
                  title="Hapus file ini dari sesi"
                  className="shrink-0 rounded-md p-1 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.75}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                    />
                  </svg>
                </button>
              )}
              <span
                className="ml-auto shrink-0 text-xs text-slate-400"
                title={entry.reason}
              >
                {entry.status === "uploading"
                  ? "Diproses…"
                  : entry.status === "success"
                    ? "Berhasil"
                    : entry.reason
                      ? `Gagal — ${entry.reason}`
                      : "Gagal"}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-5 flex items-center gap-3">
        <input
          type="url"
          value={urlInput}
          disabled={isUploading}
          onChange={(event) => setUrlInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") handleUrlSubmission();
          }}
          placeholder="Tempel tautan URL atau artikel"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="button"
          onClick={handleUrlSubmission}
          disabled={isUploading}
          className="shrink-0 rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-900 disabled:opacity-50"
        >
          {isUploading ? "Memproses…" : "Upload"}
        </button>
      </div>
    </section>
  );
}
