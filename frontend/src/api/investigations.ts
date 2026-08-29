import { apiClient } from "./client";
import type {
  PipelineRequest,
  PipelineResponse,
  InvestigationSubgraphResponse,
  InvestigationPathResponse,
  InvestigationFindingsResponse,
  InvestigationEvidenceOut,
  InvestigationSnapshotResponse,
  InvestigationSnapshotRequest
} from "../types";
import { DATA_SOURCE } from "../config";

// M8A adapter — direct consumption of real backend engine. No silent M7 fallback.

function toQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return qs ? `?${qs}` : "";
}

// Pipeline (existing)
export async function analyzeInvestigation(req: PipelineRequest): Promise<PipelineResponse> {
  if (DATA_SOURCE === "mock") {
    return { source_id: req.source_id ?? null, preprocessed_text: req.text, entities: [], resolutions: {}, relationships: [], validation_errors: [], persisted: {}, graph_sync: {} };
  }
  return apiClient.post<PipelineResponse>("/investigations/analyze", req);
}

// M8A: GET /api/investigations/subgraph
export async function getInvestigationSubgraph(params: {
  root_entity_id: string;
  depth?: number;
  case_id?: string | null;
  entity_types?: string[] | null;
  relationship_types?: string[] | null;
  max_nodes?: number;
  max_relationships?: number;
}): Promise<InvestigationSubgraphResponse> {
  if (DATA_SOURCE === "mock") {
    return { case_id: params.case_id ?? null, root_entity: { entity_id: params.root_entity_id }, depth: params.depth ?? 2, entities: [], relationships: [], statistics: {}, truncated: false, provenance: [] };
  }
  const qs = toQuery({
    root_entity_id: params.root_entity_id,
    depth: params.depth ?? 2,
    case_id: params.case_id ?? undefined,
    entity_types: params.entity_types?.join(","),
    relationship_types: params.relationship_types?.join(","),
    max_nodes: params.max_nodes,
    max_relationships: params.max_relationships
  });
  return apiClient.get<InvestigationSubgraphResponse>(`/investigations/subgraph${qs}`);
}

export async function postInvestigationSubgraph(body: {
  case_id?: string | null;
  root_entity_id: string;
  depth: number;
  entity_types?: string[] | null;
  relationship_types?: string[] | null;
  max_nodes?: number;
  max_relationships?: number;
}): Promise<InvestigationSubgraphResponse> {
  if (DATA_SOURCE === "mock") {
    return { case_id: body.case_id ?? null, root_entity: { entity_id: body.root_entity_id }, depth: body.depth, entities: [], relationships: [], statistics: {}, truncated: false, provenance: [] };
  }
  return apiClient.post<InvestigationSubgraphResponse>("/investigations/subgraph", body);
}

// M8A: GET /api/investigations/paths
export async function getInvestigationPaths(params: {
  source_id: string;
  target_id: string;
  max_depth?: number;
  case_id?: string | null;
  relationship_types?: string[] | null;
}): Promise<InvestigationPathResponse> {
  if (DATA_SOURCE === "mock") {
    return { found: false, hop_count: null, nodes: [], edges: [], relationship_sequence: [], provenance: [] };
  }
  const qs = toQuery({
    source_id: params.source_id,
    target_id: params.target_id,
    max_depth: params.max_depth ?? 6,
    case_id: params.case_id ?? undefined,
    relationship_types: params.relationship_types?.join(",")
  });
  return apiClient.get<InvestigationPathResponse>(`/investigations/paths${qs}`);
}

export async function postInvestigationPaths(body: {
  source_id: string;
  target_id: string;
  max_depth: number;
  case_id?: string | null;
  relationship_types?: string[] | null;
}): Promise<InvestigationPathResponse> {
  if (DATA_SOURCE === "mock") {
    return { found: false, hop_count: null, nodes: [], edges: [], relationship_sequence: [], provenance: [] };
  }
  return apiClient.post<InvestigationPathResponse>("/investigations/paths", body);
}

// M8A: GET /api/investigations/findings
export async function getInvestigationFindings(params: {
  case_id?: string | null;
  root_entity_id?: string | null;
  depth?: number;
}): Promise<InvestigationFindingsResponse> {
  if (DATA_SOURCE === "mock") {
    return { case_id: params.case_id ?? null, root_entity_id: params.root_entity_id ?? null, findings: [], count: 0, provenance: [] };
  }
  const qs = toQuery({
    case_id: params.case_id ?? undefined,
    root_entity_id: params.root_entity_id ?? undefined,
    depth: params.depth ?? 2
  });
  return apiClient.get<InvestigationFindingsResponse>(`/investigations/findings${qs}`);
}

// M8A: GET /api/investigations/evidence
export async function getInvestigationEvidence(params: {
  case_id?: string | null;
  root_entity_id?: string | null;
  depth?: number;
}): Promise<InvestigationEvidenceOut[]> {
  if (DATA_SOURCE === "mock") return [];
  const qs = toQuery({
    case_id: params.case_id ?? undefined,
    root_entity_id: params.root_entity_id ?? undefined,
    depth: params.depth ?? 2
  });
  return apiClient.get<InvestigationEvidenceOut[]>(`/investigations/evidence${qs}`);
}

// M8A: snapshot (adapter ready, not required for M8B UI but typed for future)
export async function getInvestigationSnapshot(params: {
  case_id?: string | null;
  root_entity_id: string;
  depth?: number;
  entity_types?: string[] | null;
  relationship_types?: string[] | null;
  include_findings?: boolean;
  include_paths?: boolean;
  max_nodes?: number;
}): Promise<InvestigationSnapshotResponse> {
  if (DATA_SOURCE === "mock") {
    return {
      snapshot_id: `mock-${params.root_entity_id}`,
      case_id: params.case_id ?? null,
      root_entity: { entity_id: params.root_entity_id },
      depth: params.depth ?? 2,
      entities: [],
      relationships: [],
      paths: [],
      findings: [],
      evidence: [],
      statistics: {},
      generated_at: new Date().toISOString(),
      provenance: []
    };
  }
  const qs = toQuery({
    case_id: params.case_id ?? undefined,
    root_entity_id: params.root_entity_id,
    depth: params.depth ?? 2,
    entity_types: params.entity_types?.join(","),
    relationship_types: params.relationship_types?.join(","),
    include_findings: params.include_findings ?? true,
    include_paths: params.include_paths ?? true,
    max_nodes: params.max_nodes ?? 200
  });
  return apiClient.get<InvestigationSnapshotResponse>(`/investigations/snapshot${qs}`);
}

export async function postInvestigationSnapshot(body: InvestigationSnapshotRequest): Promise<InvestigationSnapshotResponse> {
  if (DATA_SOURCE === "mock") {
    return {
      snapshot_id: `mock-${body.root_entity_id}`,
      case_id: body.case_id ?? null,
      root_entity: { entity_id: body.root_entity_id },
      depth: body.depth,
      entities: [],
      relationships: [],
      paths: [],
      findings: [],
      evidence: [],
      statistics: {},
      generated_at: new Date().toISOString(),
      provenance: []
    };
  }
  return apiClient.post<InvestigationSnapshotResponse>("/investigations/snapshot", body);
}
