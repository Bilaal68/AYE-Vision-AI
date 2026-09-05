export type Role = "admin" | "analyst" | "viewer";

export type ApiError = {
  error: boolean;
  status_code: number;
  detail: unknown;
};
