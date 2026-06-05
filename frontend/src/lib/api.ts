import axios from "axios";

export const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const apiOrigin = apiBaseUrl.replace(/\/api\/v1\/?$/, "");

export type BackendPaper = {
  id: string;
  title: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  categories: string[];
  status: "processing" | "completed" | "failed";
  authors: string[];
  year?: string;
  abstract?: string;
  addedAt: string;
  completedAt?: string;
  errorMessage?: string;
  entityCount?: number;
  relationCount?: number;
  downloadUrl?: string;
};

export type DocumentJobEvent = {
  document_id: string;
  status: "processing" | "completed" | "failed" | "heartbeat";
  phase: string;
  message: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
};

type ErrorPayload = {
  detail?: string;
};

export function resolveApiUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${apiOrigin}${path.startsWith("/") ? path : `/${path}`}`;
}

export function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError<ErrorPayload>(error)) {
    return error.response?.data?.detail || error.message || fallback;
  }
  return error instanceof Error ? error.message : fallback;
}

const api = axios.create({
  baseURL: apiBaseUrl,
});

export const getDocuments = async (): Promise<BackendPaper[]> => {
  const response = await api.get("/documents");
  return response.data;
};

export const getGraphData = async () => {
  const response = await api.get("/graph");
  return response.data;
};

export const getGraphSubgraph = async (paperId: string) => {
  const response = await api.get(`/graph/paper/${paperId}`);
  return response.data;
};

export const uploadDocument = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/upload/", formData);
  return response.data;
};

export function documentEventsUrl(documentId: string) {
  const wsOrigin = apiOrigin.replace(/^http/i, "ws");
  return `${wsOrigin}/api/v1/jobs/documents/${documentId}/events`;
}

export const deleteDocument = async (id: string) => {
  // Backend cascades the delete across Postgres, Neo4j, FAISS, and disk.
  // Returns 204 (clean) or 200 with a summary; we don't need the body.
  const response = await api.delete(`/documents/${id}`);
  return response.data;
};

export const sendMessage = async (message: string, sessionId?: string, topK = 5) => {
  const response = await api.post("/chat/", { message, session_id: sessionId, top_k: topK });
  return response.data;
};

export type ChatStreamEvent =
  | { type: "status"; label: string; message: string }
  | { type: "trace"; steps: string[] }
  | { type: "token"; content: string }
  | { type: "sources"; sources: string[]; reasoning_steps: string[]; graph_data?: Record<string, unknown> }
  | { type: "final"; answer: string; sources: string[]; reasoning_steps: string[]; graph_data?: Record<string, unknown> }
  | { type: "error"; message: string; reasoning_steps?: string[] };

export async function streamMessage(
  message: string,
  sessionId: string | undefined,
  handlers: {
    onEvent: (event: ChatStreamEvent) => void;
    signal?: AbortSignal;
    topK?: number;
  }
) {
  const response = await fetch(`${apiBaseUrl}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, top_k: handlers.topK ?? 5 }),
    signal: handlers.signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      handlers.onEvent(JSON.parse(line) as ChatStreamEvent);
    }
  }
  if (buffer.trim()) {
    handlers.onEvent(JSON.parse(buffer) as ChatStreamEvent);
  }
}

export default api;
