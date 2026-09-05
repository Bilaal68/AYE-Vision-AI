import { api } from "./api";

export async function listSatellite() {
  const { data } = await api.get("/satellite/");
  return data;
}
