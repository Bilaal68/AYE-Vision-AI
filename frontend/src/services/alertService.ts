import { api } from "./api";

export async function listAlerts() {
  const { data } = await api.get("/alerts/");
  return data;
}
