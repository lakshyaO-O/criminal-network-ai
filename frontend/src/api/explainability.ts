import { apiClient } from "./client";
import { DATA_SOURCE } from "../config";
import type { ExplanationResponse } from "../types";

// M9A Explainability — direct consumption of real backend engine. No silent M7/M8 fallback, no fabricated intelligence.
// In DATA_SOURCE=api every 404/500/timeout must surface as ErrorState, never derived data.
// In mock mode explainability is explicitly unavailable.

export async function getFindingExplanation(findingId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/findings/${encodeURIComponent(findingId)}`);
}

export async function getEntityExplanation(entityId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/entities/${encodeURIComponent(entityId)}`);
}

export async function getEntityCentralityExplanation(entityId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/centrality/${encodeURIComponent(entityId)}`);
}

export async function getCentralityExplanationByQuery(entityId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/centrality?entity_id=${encodeURIComponent(entityId)}`);
}

export async function getCommunitiesExplanation(entityId?: string | null, caseId?: string | null): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  if (entityId) return apiClient.get<ExplanationResponse>(`/explainability/communities/${encodeURIComponent(entityId)}`);
  const qs = caseId ? `?case_id=${encodeURIComponent(caseId)}` : entityId ? `?entity_id=${encodeURIComponent(entityId)}` : "";
  return apiClient.get<ExplanationResponse>(`/explainability/communities${qs}`);
}

export async function getBridgeExplanation(entityId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/bridges/${encodeURIComponent(entityId)}`);
}

export async function getTemporalExplanation(entityId?: string | null): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  const qs = entityId ? `?entity_id=${encodeURIComponent(entityId)}` : "";
  return apiClient.get<ExplanationResponse>(`/explainability/temporal${qs}`);
}

export async function getTransactionChainExplanation(chainId?: string | null, accountId?: string | null): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  const params = new URLSearchParams();
  if (chainId) params.set("chain_id", chainId);
  if (accountId) params.set("account_id", accountId);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiClient.get<ExplanationResponse>(`/explainability/transaction-chains${qs}`);
}

export async function getIndicatorExplanation(indicatorId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/indicators/${encodeURIComponent(indicatorId)}`);
}

export async function getRelationshipStrengthExplanation(relationshipId: string): Promise<ExplanationResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  return apiClient.get<ExplanationResponse>(`/explainability/relationship-strength/${encodeURIComponent(relationshipId)}`);
}

// Back-compat aliases used by older hooks
export const getPathExplanation = getTransactionChainExplanation;
export async function getCentralityExplanation(): Promise<ExplanationResponse> {
  throw new Error("getCentralityExplanation requires entity_id — use getEntityCentralityExplanation(entityId)");
}
