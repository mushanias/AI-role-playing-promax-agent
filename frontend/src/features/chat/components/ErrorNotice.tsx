import {
  Bot,
  CircleAlert,
  KeyRound,
  RefreshCw,
  WifiOff,
  X,
} from "lucide-react";

import type { ErrorKind, UserFacingError } from "../model/userFacingError";
import styles from "./ErrorNotice.module.css";

export interface ErrorNoticeProps {
  error: UserFacingError;
  requestContent?: string | null;
  onRetry?(): void;
  onDismiss(): void;
}

export function ErrorNotice({
  error,
  requestContent = null,
  onRetry,
  onDismiss,
}: ErrorNoticeProps) {
  return (
    <article className={styles.failure} role="alert">
      {requestContent ? (
        <div className={styles.requestBubble}>{requestContent}</div>
      ) : null}

      <div className={styles.notice} data-kind={error.kind}>
        <div className={styles.icon} aria-hidden="true">
          <ErrorIcon kind={error.kind} />
        </div>

        <div className={styles.content}>
          <h2>{error.title}</h2>
          <p>{error.description}</p>

          <div className={styles.solutions}>
            <span>可以这样解决</span>
            <ul>
              {error.solutions.map((solution) => (
                <li key={solution}>{solution}</li>
              ))}
            </ul>
          </div>

          <div className={styles.actions}>
            {error.retryable && onRetry ? (
              <button type="button" className={styles.retry} onClick={onRetry}>
                <RefreshCw size={13} />
                重试
              </button>
            ) : null}
            <button
              type="button"
              className={styles.dismiss}
              onClick={onDismiss}
            >
              知道了
            </button>
          </div>
        </div>

        <button
          type="button"
          className={styles.close}
          aria-label="关闭错误提示"
          onClick={onDismiss}
        >
          <X size={15} />
        </button>
      </div>
    </article>
  );
}

function ErrorIcon({ kind }: { kind: ErrorKind }) {
  if (kind === "network") {
    return <WifiOff size={17} />;
  }
  if (kind === "authentication") {
    return <KeyRound size={17} />;
  }
  if (kind === "model" || kind === "configuration") {
    return <Bot size={17} />;
  }
  return <CircleAlert size={17} />;
}
