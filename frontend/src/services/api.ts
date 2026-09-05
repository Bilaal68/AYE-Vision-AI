import axios from "axios";

/**
 * Axios instance shared by all API modules.
 *
 * Default base URL is `/api` so Vite can proxy to Django during `npm run dev`.
 * Docker/browser can still set VITE_API_BASE_URL to http://localhost:8000/api.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 8000,
});

export type HealthResponse = {
  status: string;
  service: string;
  database: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health/");
  return data;
}
