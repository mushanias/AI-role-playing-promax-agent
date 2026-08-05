import { useEffect, useRef, useState } from "react";

import type { PendingRequest } from "../model/types";
import { formatDuration } from "../utils/formatDuration";
import styles from "./PendingResponse.module.css";

export interface PendingResponseProps {
  request: PendingRequest;
}

export function PendingResponse({ request }: PendingResponseProps) {
  const [elapsedMs, setElapsedMs] = useState(
    () => Date.now() - request.startedAt,
  );
  const containerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const updateElapsed = () => setElapsedMs(Date.now() - request.startedAt);
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 100);
    return () => window.clearInterval(timer);
  }, [request.startedAt]);

  useEffect(() => {
    containerRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, []);

  return (
    <article ref={containerRef} className={styles.pendingTurn}>
      <section className={styles.userSection} aria-label="用户消息">
        <div className={styles.userBubble}>{request.content}</div>
      </section>

      {request.assistantContent ? (
        <section
          className={styles.assistantSection}
          aria-label="正在生成的助手回答"
          aria-live="polite"
        >
          <div className={styles.assistantContent}>
            {request.assistantContent
              .split("\n\n")
              .map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          </div>
          <GenerationStatus request={request} elapsedMs={elapsedMs} />
        </section>
      ) : (
        <GenerationStatus request={request} elapsedMs={elapsedMs} />
      )}
    </article>
  );
}

interface GenerationStatusProps {
  request: PendingRequest;
  elapsedMs: number;
}

function GenerationStatus({ request, elapsedMs }: GenerationStatusProps) {
  return (
    <div className={styles.waiting} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{request.status === "stopping" ? "正在停止" : "正在生成"}</span>
      <time>{formatDuration(elapsedMs)}</time>
    </div>
  );
}
