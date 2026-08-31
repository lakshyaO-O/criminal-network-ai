import { apiClient } from "./client";
import type { NetworkOut } from "../types";
import { DATA_SOURCE } from "../config";

export async function getNetwork(caseId: string): Promise<NetworkOut> {
  if (DATA_SOURCE === "mock") return { case_id: caseId, entities: [], relationships: [], statistics: { node_count: 0, relationship_count: 0 } };
  return apiClient.get<NetworkOut>(`/network/${encodeURIComponent(caseId)}`, { timeoutMs: 15000 });
}
