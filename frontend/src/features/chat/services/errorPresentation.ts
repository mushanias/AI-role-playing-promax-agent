import { ApiRequestError } from "../../../shared/api/ApiClient";
import type { UserFacingError } from "../model/userFacingError";

export function toUserFacingError(reason: unknown): UserFacingError {
  if (!(reason instanceof ApiRequestError)) {
    return {
      kind: "request",
      title: "操作没有完成",
      description:
        reason instanceof Error ? reason.message : "发生了未知错误，请稍后重试。",
      solutions: ["稍后重新尝试", "如果持续失败，请刷新页面后再操作"],
      retryable: true,
    };
  }

  switch (reason.code) {
    case "network_error":
    case "request_timeout":
      return {
        kind: "network",
        title: "无法连接本地后端",
        description: reason.message,
        solutions: [
          "确认 FastAPI 服务正在运行",
          "检查本机 8000 端口是否被占用",
          "恢复连接后点击重试",
        ],
        retryable: true,
      };
    case "llm_auth_error":
      return {
        kind: "authentication",
        title: "模型认证失败",
        description: reason.message,
        solutions: [
          "在左侧重新连接当前厂商的 API Key",
          "确认 API Key 与所选模型厂商一致",
          "检查账号权限、余额和 Key 是否已失效",
        ],
        retryable: true,
      };
    case "llm_network_error":
      return {
        kind: "network",
        title: "暂时无法连接模型服务",
        description: reason.message,
        solutions: [
          "检查网络或代理设置",
          "稍后重试，或切换到其他可用模型",
          "查看模型厂商的服务状态",
        ],
        retryable: true,
      };
    case "llm_response_error":
      return {
        kind: "model",
        title: "模型没有返回有效回答",
        description: reason.message,
        solutions: [
          "直接重试当前消息",
          "缩短输入内容或新建对话",
          "如果反复出现，请切换模型",
        ],
        retryable: true,
      };
    case "invalid_llm_configuration":
      return {
        kind: "configuration",
        title: "当前模型配置不可用",
        description: reason.message,
        solutions: [
          "从左侧选择后端已配置的模型",
          "确认模型名称和厂商对应",
          "重新连接该厂商的 API Key",
        ],
        retryable: false,
      };
    case "storage_io_error":
    case "storage_corruption":
      return {
        kind: "server",
        title: "本地会话数据暂时无法使用",
        description: reason.message,
        solutions: [
          "检查磁盘空间和 data 目录权限",
          "查看后端日志定位损坏的会话文件",
          "处理完成后刷新页面",
        ],
        retryable: false,
      };
    default:
      return {
        kind: reason.status >= 500 ? "server" : "request",
        title: reason.status >= 500 ? "服务暂时出现问题" : "请求没有完成",
        description: reason.message,
        solutions: ["稍后重新尝试", "如果持续失败，请查看后端日志"],
        retryable: reason.status === 0 || reason.status >= 500,
      };
  }
}

export function createPreviewError(
  preview: string | null,
): UserFacingError | null {
  if (preview === "network") {
    return toUserFacingError(
      new ApiRequestError(
        "前端无法访问本地 API 服务。",
        0,
        "network_error",
      ),
    );
  }

  if (preview === "llm") {
    return toUserFacingError(
      new ApiRequestError(
        "模型服务返回了空响应或无法解析的内容。",
        502,
        "llm_response_error",
      ),
    );
  }

  return null;
}
