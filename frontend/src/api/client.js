import axios from "axios";

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").trim();
const normalizedBaseUrl = rawBaseUrl.replace(/\/+$/, "");
const apiKey = (import.meta.env.VITE_API_KEY || "").trim();

export const API_BASE_URL = normalizedBaseUrl;

export const apiClient = axios.create({
  baseURL: normalizedBaseUrl || undefined,
  timeout: 30000,
  headers: apiKey ? { "X-API-Key": apiKey } : {},
});

export async function healthCheck() {
  const response = await apiClient.get("/health");
  return response.data;
}

export async function simulateDiscount(category, payload) {
  const response = await apiClient.post(`/simulate/discount/${encodeURIComponent(category)}`, payload);
  return response.data;
}

