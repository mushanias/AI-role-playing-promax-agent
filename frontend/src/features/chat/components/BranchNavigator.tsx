import { ChevronLeft, ChevronRight } from "lucide-react";

import { IconButton } from "../../../shared/ui/IconButton";
import styles from "./BranchNavigator.module.css";

export interface BranchNavigatorProps {
  current: number;
  total: number;
  disabled?: boolean;
  onPrevious(): void;
  onNext(): void;
}

export function BranchNavigator({
  current,
  total,
  disabled = false,
  onPrevious,
  onNext,
}: BranchNavigatorProps) {
  if (total <= 1) {
    return null;
  }

  return (
    <nav className={styles.navigator} aria-label="消息分支">
      <IconButton
        label="上一个分支"
        className={styles.arrow}
        disabled={disabled || current <= 1}
        onClick={onPrevious}
      >
        <ChevronLeft size={15} strokeWidth={1.9} />
      </IconButton>

      <span className={styles.counter} aria-live="polite">
        {current} / {total}
      </span>

      <IconButton
        label="下一个分支"
        className={styles.arrow}
        disabled={disabled || current >= total}
        onClick={onNext}
      >
        <ChevronRight size={15} strokeWidth={1.9} />
      </IconButton>
    </nav>
  );
}
