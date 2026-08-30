export type SourceType = "pdf" | "docx" | "pptx" | "txt" | "url";

export interface SessionSummary {
  id: number;
  title: string;
  created_at: string;
  source_count: number;
}

export interface SessionDocument {
  id: number;
  source_type: string;
  filename?: string | null;
  url?: string | null;
  source_name?: string | null;
  chunk_count?: number;
}

export interface FileIngestItem {
  filename: string;
  success: boolean;
  message: string;
  document_ids: string[];
}

export interface MultiIngestResponse {
  success: boolean;
  session_id: number;
  files: FileIngestItem[];
}

export interface DeleteDocumentResponse {
  success: boolean;
  session_id: number;
  filename?: string | null;
  url?: string | null;
  documents_removed: number;
}

export interface SessionMessage {
  id: number;
  prompt: string;
  generated_response: string;
  citations: Citation[];
}

export interface SessionDetail {
  session_id: number;
  title: string;
  documents: SessionDocument[];
  messages: SessionMessage[];
}

export interface Citation {
  source_name?: string | null;
  source_type?: string | null;
  filename?: string | null;
  url?: string | null;
}

export interface ChatMessage {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  includeCitations?: boolean;
}

export interface ToastItem {
  id: number;
  type: "success" | "error" | "info";
  message: string;
}
