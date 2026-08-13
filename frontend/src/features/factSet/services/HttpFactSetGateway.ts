import { apiRequest } from "../../../shared/api/ApiClient";
import type { FactSet } from "../model/types";
import type { FactSetGateway } from "./FactSetGateway";

interface FactSetDto {
  content: string;
  updated_at: string | null;
}

export class HttpFactSetGateway implements FactSetGateway {
  async get(): Promise<FactSet> {
    const factSet = await apiRequest<FactSetDto>("/fact-set", {
      timeoutMs: 5_000,
    });
    return toFactSet(factSet);
  }

  async replace(content: string): Promise<FactSet> {
    const factSet = await apiRequest<FactSetDto>("/fact-set", {
      method: "PUT",
      body: JSON.stringify({ content }),
    });
    return toFactSet(factSet);
  }
}

function toFactSet(factSet: FactSetDto): FactSet {
  return {
    content: factSet.content,
    updatedAt: factSet.updated_at,
  };
}
