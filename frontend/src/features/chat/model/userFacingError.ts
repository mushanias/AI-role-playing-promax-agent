export type ErrorKind =
  | "network"
  | "authentication"
  | "model"
  | "configuration"
  | "server"
  | "request";

export interface UserFacingError {
  kind: ErrorKind;
  title: string;
  description: string;
  solutions: string[];
  retryable: boolean;
}
