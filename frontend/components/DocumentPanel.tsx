"use client";

import type { SessionDocument } from "@/types/dashboard";

interface DocumentPanelProps {
  documents: SessionDocument[];
  isLoading?: boolean;
  onDelete: (document: SessionDocument) => void;
  deletingId?: number | null;
}

export default function DocumentPanel({
  documents,
  isLoading,
  onDelete,
  deletingId,
}: DocumentPanelProps) {
  return (
    <section className="rounded-sm border border-white/10 bg-carbon-panel p-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-pure-signal">Dokumen Sumber</h3>
        </div>
        <span className="rounded-full border border-periwinkle-veil/50 px-2.5 py-0.5 font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
          {documents.length}
        </span>
      </div>

      {isLoading ? (
        <div className="mt-3 space-y-2">
          <div className="h-10 animate-pulse rounded-sm bg-graphite-lift" />
          <div className="h-10 animate-pulse rounded-sm bg-graphite-lift" />
        </div>
      ) : documents.length === 0 ? (
        <p className="mt-3 text-sm leading-relaxed text-soft-mist/55">
          Belum ada dokumen. Unggah file atau tautan untuk mulai riset.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {documents.map((document) => (
            <li
              key={document.id}
              className="group flex items-center gap-2 rounded-sm border border-white/10 bg-graphite-lift/50 px-3 py-2 text-sm"
            >
              <svg
                className="h-4 w-4 shrink-0 text-soft-mist/50"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                />
              </svg>
              <span className="basis-0 min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  {document.document_label && (
                    <span className="shrink-0 rounded-sm border border-periwinkle-veil/40 bg-periwinkle-veil/10 px-1.5 py-0.5 font-mono text-caption uppercase tracking-tight text-periwinkle-veil">
                      {document.document_label}
                    </span>
                  )}
                  <span className="min-w-0 truncate text-soft-mist">
                    {document.source_name ?? document.filename ?? document.url}
                  </span>
                </span>
                {(document.authors || document.publication_year) && (
                  <span className="mt-0.5 block truncate text-xs text-soft-mist/55">
                    {Array.isArray(document.authors)
                      ? document.authors.join(", ")
                      : document.authors ?? ""}
                    {document.publication_year
                      ? ` (${document.publication_year})`
                      : ""}
                  </span>
                )}
              </span>
              <button
                type="button"
                onClick={() => onDelete(document)}
                disabled={deletingId === document.id}
                aria-label={`Hapus ${document.source_name ?? document.filename ?? "dokumen"}`}
                className="shrink-0 rounded-sm p-1 text-soft-mist/45 transition-colors hover:bg-rose-500/15 hover:text-rose-400 disabled:opacity-50"
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
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}