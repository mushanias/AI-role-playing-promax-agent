export function formatDuration(durationMs: number): string {
  const safeDuration = Math.max(0, durationMs);

  if (safeDuration < 60_000) {
    return `${(safeDuration / 1000).toFixed(1)} 秒`;
  }

  const minutes = Math.floor(safeDuration / 60_000);
  const seconds = Math.floor((safeDuration % 60_000) / 1000);
  return `${minutes} 分 ${seconds} 秒`;
}
