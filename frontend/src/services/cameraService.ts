import { api } from "./api";

/** Placeholder. Camera endpoints are not implemented yet. */
export async function listCameras() {
  const { data } = await api.get("/cameras/");
  return data;
}
