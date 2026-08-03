import { apiRequest, ApiRequestError } from "../../../shared/api/ApiClient";
import type { AuthSession } from "../model/types";
import type { AuthGateway } from "./AuthGateway";

export class HttpAuthGateway implements AuthGateway {
  async getSession(): Promise<AuthSession | null> {
    try {
      return await apiRequest<AuthSession>("/auth/session");
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 401) {
        return null;
      }
      throw error;
    }
  }

  login(username: string, password: string): Promise<AuthSession> {
    return apiRequest<AuthSession>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  }

  logout(): Promise<void> {
    return apiRequest<void>("/auth/logout", { method: "POST" });
  }
}
