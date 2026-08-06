import { useState } from "react";
import { ArrowUp, GitBranch, LoaderCircle } from "lucide-react";

import styles from "./LoginPage.module.css";

export interface LoginPageProps {
  checking: boolean;
  submitting: boolean;
  errorMessage: string | null;
  onLogin(username: string, password: string): Promise<boolean>;
}

export function LoginPage({
  checking,
  submitting,
  errorMessage,
  onLogin,
}: LoginPageProps) {
  const [username, setUsername] = useState("123456");
  const [password, setPassword] = useState("");
  const busy = checking || submitting;
  const inputsDisabled = submitting;

  return (
    <main className={styles.page}>
      <section className={styles.login} aria-labelledby="login-title">
        <span className={styles.mark} aria-hidden="true">
          <GitBranch size={19} />
        </span>
        <div className={styles.heading}>
          <h1 id="login-title">登录分支对话</h1>
          <p>{checking ? "正在确认本地会话" : "使用你的本地账号继续"}</p>
        </div>

        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault();
            if (!username.trim() || !password || busy) return;
            void onLogin(username.trim(), password);
          }}
        >
          <label className={styles.field}>
            <span>用户名</span>
            <input
              value={username}
              autoComplete="username"
              disabled={inputsDisabled}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className={styles.field}>
            <span>密码</span>
            <input
              type="password"
              value={password}
              autoComplete="current-password"
              autoFocus={!checking}
              disabled={inputsDisabled}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          {errorMessage ? (
            <p className={styles.error} role="alert">
              {errorMessage}
            </p>
          ) : null}

          <button
            type="submit"
            className={styles.submit}
            disabled={busy || !username.trim() || !password}
          >
            {busy ? (
              <LoaderCircle className={styles.spinner} size={17} />
            ) : (
              <ArrowUp size={17} />
            )}
            <span>{checking ? "检查中" : submitting ? "登录中" : "登录"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}
