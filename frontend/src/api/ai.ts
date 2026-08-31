import { apiClient } from "./client";
import { DATA_SOURCE } from "../config";
import type {
  AIStatusResponse,
  AIExtractEntitiesResponse,
  AIExtractRelationshipsResponse,
  AIAnalyzeResponse,
  AIEntityMention,
} from "../types";

// M12A AI adapter — uses centralized apiClient only, 8s timeout via client, no silent fallbacks.
// Mock mode: throws "AI unavailable in mock mode" — caller maps to Empty/ErrorState, never fabricated.

export async function getAIStatus(): Promise<AIStatusResponse> {
  if (DATA_SOURCE === "mock") throw new Error("AI unavailable in mock mode");
  return apiClient.get<AIStatusResponse>("/ai/status");
}

export async function extractEntities(params: {
  text: string;
  source_id?: string | null;
  provider?: string | null;
}): Promise<AIExtractEntitiesResponse> {
  if (DATA_SOURCE === "mock") throw new Error("AI unavailable in mock mode");
  const body: Record<string, unknown> = { text: params.text };
  if (params.source_id !== undefined && params.source_id !== null) body.source_id = params.source_id;
  if (params.provider) body.provider = params.provider;
  return apiClient.post<AIExtractEntitiesResponse>("/ai/extract/entities", body);
}

export async function extractRelationships(params: {
  text: string;
  source_id?: string | null;
  entities: AIEntityMention[];
  structured_records?: Record<string, unknown>[];
  provider?: string | null;
}): Promise<AIExtractRelationshipsResponse> {
  if (DATA_SOURCE === "mock") throw new Error("AI unavailable in mock mode");
  const body: Record<string, unknown> = {
    text: params.text,
    entities: params.entities,
    structured_records: params.structured_records ?? [],
  };
  if (params.source_id !== undefined && params.source_id !== null) body.source_id = params.source_id;
  if (params.provider) body.provider = params.provider;
  return apiClient.post<AIExtractRelationshipsResponse>("/ai/extract/relationships", body);
}

export async function analyzeWithAI(params: {
  analysis_type: string;
  case_id?: string | null;
  root_entity_id?: string | null;
  text?: string | null;
  graph_snapshot?: Record<string, unknown> | null;
  provider?: string | null;
}): Promise<AIAnalyzeResponse> {
  if (DATA_SOURCE === "mock") throw new Error("AI unavailable in mock mode");
  const body: Record<string, unknown> = {
    analysis_type: params.analysis_type,
  };
  if (params.case_id !== undefined && params.case_id !== null) body.case_id = params.case_id;
  if (params.root_entity_id !== undefined && params.root_entity_id !== null) body.root_entity_id = params.root_entity_id;
  if (params.text !== undefined && params.text !== null) body.text = params.text;
  if (params.graph_snapshot !== undefined && params.graph_snapshot !== null) body.graph_snapshot = params.graph_snapshot;
  if (params.provider) body.provider = params.provider;
  return apiClient.post<AIAnalyzeResponse>("/ai/analyze", body);
}
