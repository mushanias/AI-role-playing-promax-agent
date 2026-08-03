import { useEffect, useState } from "react";

import { API_BASE_URL } from "../../config/runtime";

export type BackendConnectionStatus =
  | "checking"
  | "connected"
  | "disconnected";

const CONNECTED_CHECK_INTERVAL_MS = 15_000;
const DISCONNECTED_CHECK_INTERVAL_MS = 5_000;
const HEALTH_CHECK_TIMEOUT_MS = 2_500;

export function useBackendConnection(): BackendConnectionStatus {
  const [status, setStatus] = useState<BackendConnectionStatus>("checking");

  useEffect(() => {
    let isActive = true;
    let nextCheckTimer: number | null = null;
    let activeController: AbortController | null = null;

    const scheduleNextCheck = (nextStatus: BackendConnectionStatus) => {
      if (nextCheckTimer !== null) {
        window.clearTimeout(nextCheckTimer);
      }
      nextCheckTimer = window.setTimeout(
        checkConnection,
        nextStatus === "connected"
          ? CONNECTED_CHECK_INTERVAL_MS
          : DISCONNECTED_CHECK_INTERVAL_MS,
      );
    };

    const checkConnection = async () => {
      if (nextCheckTimer !== null) {
        window.clearTimeout(nextCheckTimer);
        nextCheckTimer = null;
      }

      activeController?.abort();
      const controller = new AbortController();
      activeController = controller;
      const timeout = window.setTimeout(
        () => controller.abort(),
        HEALTH_CHECK_TIMEOUT_MS,
      );

      let nextStatus: BackendConnectionStatus = "disconnected";

      try {
        const response = await fetch(`${API_BASE_URL}/`, {
          cache: "no-store",
          signal: controller.signal,
        });
        nextStatus = response.ok ? "connected" : "disconnected";
      } catch {
        nextStatus = "disconnected";
      } finally {
        window.clearTimeout(timeout);
      }

      if (!isActive) {
        return;
      }

      setStatus(nextStatus);
      scheduleNextCheck(nextStatus);
    };

    const markOffline = () => {
      activeController?.abort();
      setStatus("disconnected");
      scheduleNextCheck("disconnected");
    };

    void checkConnection();
    window.addEventListener("online", checkConnection);
    window.addEventListener("offline", markOffline);

    return () => {
      isActive = false;
      activeController?.abort();
      if (nextCheckTimer !== null) {
        window.clearTimeout(nextCheckTimer);
      }
      window.removeEventListener("online", checkConnection);
      window.removeEventListener("offline", markOffline);
    };
  }, []);

  return status;
}
