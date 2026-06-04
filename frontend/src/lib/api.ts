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
  status: "indexed" | "needs_review";
  authors: string[];
  year?: string;
  abstract?: string;
  addedAt: string;
  downloadUrl?: string;
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

export const sendMessage = async (message: string, sessionId?: string, topK = 5) => {
  const response = await api.post("/chat/", { message, session_id: sessionId, top_k: topK });
  return response.data;
};

export default api;
