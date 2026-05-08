import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

export const getDocuments = async () => {
  const response = await api.get("/documents");
  return response.data;
};

export const uploadDocument = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/upload", formData);
  return response.data;
};

export const sendMessage = async (message: string, sessionId?: string) => {
  const response = await api.post("/chat", { message, session_id: sessionId });
  return response.data;
};

export default api;
