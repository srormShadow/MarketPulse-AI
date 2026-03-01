import axios from "axios";

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").trim();
const normalizedBaseUrl = rawBaseUrl.replace(/\/+$/, "");

export const API_BASE_URL = normalizedBaseUrl;

export const apiClient = axios.create({
  baseURL: normalizedBaseUrl || undefined,
  timeout: 8000,
});

export async function healthCheck() {
  const response = await apiClient.get("/health");
  return response.data;
}

