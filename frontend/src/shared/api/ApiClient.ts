import { API_BASE_URL } from "../../config/runtime";

export const AUTH_REQUIRED_EVENT = "versioned-chat:auth-required";

interface BackendErrorPayload {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: string | Array<{ msg?: string }>;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export interface ApiRequestInit extends RequestInit {
  timeoutMs?: number;
}

export async function apiRequest<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const { timeoutMs, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);
  headers.set("Accept", "application/json");

  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  const timeoutController = timeoutMs ? new AbortController() : null;
  const timeout = timeoutController
    ? window.setTimeout(() => timeoutController.abort(), timeoutMs)
    : null;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...requestInit,
      credentials: requestInit.credentials ?? "include",
      headers,
      signal: timeoutController?.signal ?? requestInit.signal,
    });
  } catch {
    if (timeoutController?.signal.aborted) {
      throw new ApiRequestError(
        "连接本地后端超时，请确认服务正在运行",
        0,
        "request_timeout",
      );
    }
    throw new ApiRequestError(
      "无法连接后端，请确认 FastAPI 已在 8000 端口启动",
      0,
      "network_error",
    );
  } finally {
    if (timeout !== null) {
      window.clearTimeout(timeout);
    }
  }

  const payload = (await response
    .json()
    .catch(() => null)) as BackendErrorPayload | T | null;

  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") {
      window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
    }
    const errorPayload = payload as BackendErrorPayload | null;
    const validationMessage = Array.isArray(errorPayload?.detail)
      ? errorPayload.detail[0]?.msg
      : errorPayload?.detail;
    throw new ApiRequestError(
      errorPayload?.error?.message ||
        validationMessage ||
        `后端请求失败（${response.status}）`,
      response.status,
      errorPayload?.error?.code,
    );
  }

  return payload as T;
}
