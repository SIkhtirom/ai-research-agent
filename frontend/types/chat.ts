export interface Citation {
  index: number;
  source_type?: string;
  filename?: string | null;
  url?: string | null;
  source_name?: string | null;
}

export interface ChatRequest {
  query: string;
  sessionId?: number;
}

export interface ChatResponse {
  session_id: number;
  generated_response: string;
  citations: Citation[];
}
