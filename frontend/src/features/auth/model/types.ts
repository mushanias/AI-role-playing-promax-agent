export interface AuthSession {
  authenticated: boolean;
  username: string;
}

export type AuthStatus = "checking" | "authenticated" | "unauthenticated";
