import { apiClient } from "./client";
import type { EntityOut, EntityRelationshipsOut, ExtractionRequest, ExtractionResponse, HealthResponse, NeighborhoodOut, RelationshipExtractionRequest, RelationshipExtractionResponse } from "../types";
import { DATA_SOURCE } from "../config";
import { entities as mockEntities, relationships as mockRels } from "../data/mockData";

export async function getHealth(): Promise<HealthResponse> {
  if (DATA_SOURCE === "mock") return { status: "ok", service: "criminal-network-analysis", version: "mock-1.0.0", neo4j_connected: null };
  return apiClient.get<HealthResponse>("/health");
}

export async function extractEntities(req: ExtractionRequest): Promise<ExtractionResponse> {
  if (DATA_SOURCE === "mock") return { source_id: req.source_id ?? null, entities: [], entity_count: 0 };
  return apiClient.post<ExtractionResponse>("/extraction/entities", req);
}

export async function extractRelationships(req: RelationshipExtractionRequest): Promise<RelationshipExtractionResponse> {
  if (DATA_SOURCE === "mock") return { source_id: req.source_id ?? null, relationships: [], relationship_count: 0 };
  return apiClient.post<RelationshipExtractionResponse>("/extraction/relationships", req);
}

export async function getEntity(entityId: string): Promise<EntityOut> {
  if (DATA_SOURCE === "mock") {
    const e = mockEntities.find(x => x.id === entityId);
    if (!e) throw new Error(`Entity ${entityId} not found`);
    return { entity_id: e.id, entity_type: e.type, full_name: e.displayName, metadata: e.metadata } as EntityOut;
  }
  return apiClient.get<EntityOut>(`/entities/${encodeURIComponent(entityId)}`);
}

export async function getEntityRelationships(entityId: string): Promise<EntityRelationshipsOut> {
  if (DATA_SOURCE === "mock") {
    const rels = mockRels.filter(r => r.source === entityId || r.target === entityId).map(r => ({
      relationship_id: r.id, source: { entity_id: r.source }, target: { entity_id: r.target }, relationship_type: r.type, confidence: r.confidence, extraction_method: r.extractionMethod ?? "mock", source_id: r.sourceId, metadata: {}
    }));
    return { entity_id: entityId, relationships: rels };
  }
  return apiClient.get<EntityRelationshipsOut>(`/entities/${encodeURIComponent(entityId)}/relationships`, { timeoutMs: 15000 });
}

export async function getNeighborhood(entityId: string, depth = 1): Promise<NeighborhoodOut> {
  if (DATA_SOURCE === "mock") {
    const rels = mockRels.filter(r => r.source === entityId || r.target === entityId);
    const edges = rels.map(r => ({ from: r.source, to: r.target, relationship_type: r.type }));
    const ids = new Set<string>([entityId, ...rels.flatMap(r => [r.source, r.target])]);
    const nodes = Array.from(ids).map(id => ({ entity_id: id, depth: id === entityId ? 0 : 1 }));
    return { start_entity_id: entityId, depth, nodes, edges };
  }
  return apiClient.get<NeighborhoodOut>(`/entities/${encodeURIComponent(entityId)}/neighborhood?depth=${depth}`);
}
