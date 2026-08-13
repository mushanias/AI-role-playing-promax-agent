import type { FactSet } from "../model/types";

export interface FactSetGateway {
  get(): Promise<FactSet>;
  replace(content: string): Promise<FactSet>;
}
