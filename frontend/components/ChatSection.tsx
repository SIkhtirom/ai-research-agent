"use client";

import { useState } from "react";

import type { ChatMessage, Citation } from "@/types/dashboard";

interface ChatSectionProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendQuery: (query: string) => void;
}

function citationLabel(citation: Citation): string {
  return citation.source_name ?? citation.filename ?? citation.url ?? "Sumber";
}

export default function ChatSection({
  messages,
  isLoading,
  onSendQuery,
}: ChatSectionProps) {
  const [queryInput, setQueryInput] = useState("");

  const handleSubmit = () => {
    const trimmedQuery = queryInput.trim();
    if (!trimmedQuery || isLoading) return;
    onSendQuery(trimmedQuery);
    setQueryInput("");
  };

  return (
    <section className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <h3 className="text-base font-semibold text-slate-900">Tanya Asisten</h3>
        {messages.length === 0 && !isLoading && (
          <span className="text-xs text-slate-400">
            Belum ada pertanyaan pada sesi ini
          </span>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                message.role === "user"
                  ? "bg-indigo-600 text-white"
                  : "border border-slate-200 bg-slate-50"
              }`}
            >
              <p className="whitespace-pre-line text-sm leading-relaxed">
                {message.content}
              </p>

              {message.citations &&
                message.citations.length > 0 &&
                message.role === "assistant" &&
                (message.includeCitations ||
                  (message.includeCitations === undefined &&
                    message.citations.length > 0)) && (
                  <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs font-semibold text-slate-500">
                      Kutipan Sumber
                    </p>
                    <ul className="mt-2 space-y-1">
                      {message.citations.map((citation, index) => (
                        <li
                          key={`${message.id}-citation-${index}`}
                          className="flex items-start gap-2 text-xs text-slate-600"
                        >
                          <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded bg-indigo-100 text-[10px] font-semibold text-indigo-700">
                            {index + 1}
                          </span>
                          <span className="truncate">{citationLabel(citation)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <span className="flex space-x-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: "0ms" }} />
                <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: "150ms" }} />
                <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: "300ms" }} />
              </span>
              <span className="text-sm text-slate-500">Asisten sedang berpikir…</span>
            </div>
          </div>
        )}

        {messages.length === 0 && !isLoading && (
          <div className="flex h-full flex-col items-center justify-center py-12 text-center">
            <svg
              className="mb-3 h-12 w-12 text-slate-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"
              />
            </svg>
            <p className="text-sm text-slate-400">
              Tulis pertanyaan tentang sumber riset Anda di bawah.
            </p>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 px-5 py-4">
        <div className="flex items-center gap-3">
          <textarea
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Tulis pertanyaan riset Anda…"
            rows={2}
            className="min-h-[2.75rem] flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm leading-relaxed text-slate-700 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isLoading}
            className="flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
              />
            </svg>
            Kirim
          </button>
        </div>
      </div>
    </section>
  );
}
