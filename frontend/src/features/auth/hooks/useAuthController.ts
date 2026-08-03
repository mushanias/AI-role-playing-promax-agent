import { useCallback, useEffect, useState } from "react";

import {
  AUTH_REQUIRED_EVENT,
  ApiRequestError,
} from "../../../shared/api/ApiClient";
import type { AuthStatus } from "../model/types";
import type { AuthGateway } from "../services/AuthGateway";

export interface AuthController {
  status: AuthStatus;
  username: string | null;
  isSubmitting: boolean;
  errorMessage: string | null;
  login(username: string, password: string): Promise<boolean>;
  logout(): Promise<void>;
}

export function useAuthController(gateway: AuthGateway): AuthController {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [username, setUsername] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void gateway
      .getSession()
      .then((session) => {
        if (!active) return;
        setUsername(session?.username ?? null);
        setStatus(session ? "authenticated" : "unauthenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setStatus("unauthenticated");
        setErrorMessage(toAuthErrorMessage(error));
      });

    const requireLogin = () => {
      setUsername(null);
      setStatus("unauthenticated");
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, requireLogin);

    return () => {
      active = false;
      window.removeEventListener(AUTH_REQUIRED_EVENT, requireLogin);
    };
  }, [gateway]);

  const login = useCallback(
    async (nextUsername: string, password: string): Promise<boolean> => {
      setIsSubmitting(true);
      setErrorMessage(null);
      try {
        const session = await gateway.login(nextUsername, password);
        setUsername(session.username);
        setStatus("authenticated");
        return true;
      } catch (error) {
        setErrorMessage(toAuthErrorMessage(error));
        return false;
      } finally {
        setIsSubmitting(false);
      }
    },
    [gateway],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await gateway.logout();
    } finally {
      setUsername(null);
      setStatus("unauthenticated");
      setErrorMessage(null);
    }
  }, [gateway]);

  return {
    status,
    username,
    isSubmitting,
    errorMessage,
    login,
    logout,
  };
}

function toAuthErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 401) {
      return "用户名或密码错误";
    }
    return error.message;
  }
  return "登录失败，请稍后重试";
}
