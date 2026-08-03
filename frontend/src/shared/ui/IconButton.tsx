import type { ButtonHTMLAttributes, ReactNode } from "react";

import styles from "./IconButton.module.css";

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> {
  label: string;
  children: ReactNode;
  tone?: "ghost" | "solid";
}

export function IconButton({
  label,
  children,
  tone = "ghost",
  className = "",
  ...buttonProps
}: IconButtonProps) {
  const classes = [styles.button, styles[tone], className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={classes}
      {...buttonProps}
    >
      {children}
    </button>
  );
}
