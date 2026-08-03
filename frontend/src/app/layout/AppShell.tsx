import type { ReactNode } from "react";

import styles from "./AppShell.module.css";

export interface AppShellProps {
  sidebar: ReactNode;
  children: ReactNode;
  sidebarOpen: boolean;
  onCloseSidebar(): void;
}

export function AppShell({
  sidebar,
  children,
  sidebarOpen,
  onCloseSidebar,
}: AppShellProps) {
  return (
    <div
      className={styles.shell}
      data-sidebar-open={sidebarOpen ? "true" : "false"}
    >
      <aside className={styles.sidebar}>{sidebar}</aside>

      <button
        type="button"
        className={styles.overlay}
        aria-label="关闭侧边栏"
        onClick={onCloseSidebar}
      />

      <div className={styles.content}>{children}</div>
    </div>
  );
}
