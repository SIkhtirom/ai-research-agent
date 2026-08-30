export interface UrlIngestionRequest {
  url: string;
  sessionId?: number;
}

export interface IngestionResponse {
  success: boolean;
  message: string;
  session_id: number;
  document_ids: string[];
  metadata: Record<string, unknown>;
}
