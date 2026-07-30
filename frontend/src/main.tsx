import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

function App() {
  return <main>学习路径 Agent 正在初始化</main>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
