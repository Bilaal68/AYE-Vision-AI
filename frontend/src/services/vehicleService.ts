import { api } from "./api";

export async function listVehicles() {
  const { data } = await api.get("/vehicles/");
  return data;
}
