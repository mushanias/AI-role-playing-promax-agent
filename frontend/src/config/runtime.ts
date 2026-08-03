const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL as
  | string
  | undefined;

export const API_BASE_URL = (
  configuredApiBaseUrl?.trim() || "/api"
).replace(/\/$/, "");
