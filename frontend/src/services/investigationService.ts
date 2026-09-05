import { api } from "./api";

export async function listInvestigations() {
  const { data } = await api.get("/investigations/");
  return data;
}
