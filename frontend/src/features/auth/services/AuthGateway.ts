import type { AuthSession } from "../model/types";

export interface AuthGateway {
  getSession(): Promise<AuthSession | null>;
  login(username: string, password: string): Promise<AuthSession>;
  logout(): Promise<void>;
}
