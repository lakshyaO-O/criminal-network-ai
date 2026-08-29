// Canonical domain model adapted for frontend — keep strict, no any
export type CanonicalEntityType =
  | "Person" | "Organization" | "PhoneNumber" | "Vehicle" | "Location"
  | "FinancialAccount" | "Transaction" | "Communication" | "Case" | "FIR" | "Event" | "Evidence";
export type EntityType = "Person" | "Organization" | "Phone" | "Vehicle" | "Location" | "Account";
export const canonicalToDisplay: Record<string, EntityType> = {
  Person: "Person", Organization: "Organization", PhoneNumber: "Phone", Phone: "Phone",
  Vehicle: "Vehicle", Location: "Location", FinancialAccount: "Account", Account: "Account",
  Transaction: "Account", Communication: "Phone", Case: "Organization", FIR: "Organization", Event: "Location", Evidence: "Organization"
};
export const displayToCanonical: Record<EntityType, CanonicalEntityType> = {
  Person: "Person", Organization: "Organization", Phone: "PhoneNumber", Vehicle: "Vehicle", Location: "Location", Account: "FinancialAccount"
};
export type CanonicalRelationshipType =
  | "KNOWS" | "CALLED" | "TRANSFERRED_TO" | "LOCATED_AT" | "TRAVELED_TO" | "ASSOCIATED_WITH" | "WORKS_FOR" | "OWNS" | "USED" | "MENTIONED_IN" | "RELATED_TO_CASE";
export type RelationshipType = CanonicalRelationshipType;

export interface Entity {
  id: string; type: EntityType; canonicalType?: CanonicalEntityType; displayName: string;
  confidence: number; relationshipCount: number; sourceCount: number; associatedCases: string[]; lastObserved: string; metadata: Record<string, string>;
}
export interface Relationship {
  id: string; source: string; target: string; type: RelationshipType; confidence: number; timestamp: string | null; sourceId: string; extractionMethod?: string; metadata?: Record<string, unknown>;
}
export interface TimelineEvent { id: string; timestamp: string; eventType: string; entities: string[]; source: string; confidence: number; description: string; }
export interface Alert {
  id: string; entityId: string; indicator: string; title: string; reason: string; evidence: string[]; severity: "low" | "medium" | "high"; timestamp: string;
  indicator_type?: string; score?: number; explanation?: string;
}
export interface CaseItem { id: string; number: string; title: string; status: "open" | "under_review" | "closed"; entityCount: number; description?: string; case_type?: string; }
export interface Evidence { id: string; title: string; source: string; timestamp: string; }
export interface NetworkData { entities: Entity[]; relationships: Relationship[]; }
export interface InvestigationData {
  entities: Entity[]; relationships: Relationship[]; timelineEvents: TimelineEvent[]; alerts: Alert[]; cases: CaseItem[]; allSearchItems: { id: string; label: string; type: string }[];
}

// API contract types — based on backend/schemas.py and docs/api.md
export interface HealthResponse { status: string; service: string; version: string; neo4j_connected?: boolean | null; database?: Record<string, string>; graph?: Record<string, string>; }
export interface ExtractionRequest { text: string; source_id?: string | null; use_spacy?: boolean; }
export interface ExtractedEntityOut { text: string; entity_type: string; start_offset: number; end_offset: number; normalized_value?: string | null; entity_id?: string | null; confidence?: number | null; extraction_method: string; source_id?: string | null; metadata: Record<string, unknown>; }
export interface ExtractionResponse { source_id?: string | null; entities: ExtractedEntityOut[]; entity_count: number; }
export interface RelationshipExtractionRequest { text: string; source_id?: string | null; entities?: ExtractedEntityOut[]; structured_records?: Record<string, unknown>[]; }
export interface RelationshipOut { relationship_id: string; source: Record<string, unknown>; target: Record<string, unknown>; relationship_type: string; timestamp?: string | null; confidence: number; extraction_method: string; source_id?: string | null; metadata: Record<string, unknown>; }
export interface RelationshipExtractionResponse { source_id?: string | null; relationships: RelationshipOut[]; relationship_count: number; }
export interface PipelineRequest { text: string; source_id?: string | null; structured_records?: Record<string, unknown>[]; use_spacy?: boolean; persist?: boolean; sync_graph?: boolean; }
export interface PipelineResponse { source_id?: string | null; preprocessed_text: string; entities: ExtractedEntityOut[]; resolutions: Record<string, unknown[]>; relationships: RelationshipOut[]; validation_errors: string[]; persisted: Record<string, number>; graph_sync: Record<string, number>; }
export interface EntityOut { entity_id: string; entity_type: string; full_name?: string | null; name?: string | null; number?: string | null; registration_number?: string | null; account_number?: string | null; case_number?: string | null; fir_number?: string | null; title?: string | null; status?: string | null; created_at?: string | null; metadata: Record<string, unknown>; [k: string]: unknown; }
export interface EntityRelationshipsOut { entity_id: string; relationships: RelationshipOut[]; }
export interface NeighborhoodOut { start_entity_id: string; depth: number; nodes: { entity_id: string; depth: number }[]; edges: { from: string; to: string; relationship_type: string }[]; }
export interface ShortestPathOut { found: boolean; length: number | null; entities: string[]; relationships: string[]; }
export interface CaseOut { case_id: string; case_number: string; title: string; description: string; case_type: string; status: string; assigned_to?: string | null; opened_at?: string | null; metadata: Record<string, unknown>; }
export interface NetworkOut { case_id: string; entities: EntityOut[]; relationships: RelationshipOut[]; statistics: Record<string, unknown>; }
export interface IndicatorOut { entity_id: string; indicator: string; reason: string; evidence: string[]; }
export interface StructuredIndicatorOut { indicator_id: string; indicator_type: string; severity: string; entity_ids: string[]; relationship_ids: string[]; score: number; explanation: string; evidence: string[]; created_at: string; }
export interface CentralityResponse { centrality: Record<string, Record<string, number>>; explanations: Record<string, string>; }
export interface CommunityDetailOut { community_id: string; members: string[]; size: number; internal_edges: number; density: number; }
export interface BridgeDetailOut { entity_id: string; entity_type: string; metric: string; score: number; explanation: string; evidence: string[]; }
export interface TemporalIndicatorOut { indicator_type: string; time_window: string; entity_ids: string[]; observed_count: number; baseline: { mean: number; std: number; threshold: number }; explanation: string; evidence: string[]; }
export interface TransactionChainOut { chain_id: string; source_account: string; intermediate_accounts: string[]; destination_account: string; hop_count: number; evidence: string[]; explanation: string; }
export interface RelationshipStrengthOut { relationship_id: string; relationship_type: string; source_id: string; target_id: string; interaction_strength: number; factors: Record<string, unknown>; explanation: string; }
export interface AnalysisResponse {
  counts: Record<string, unknown>; entity_type_counts: Record<string, number>; relationship_type_counts: Record<string, number>;
  degree_statistics: Record<string, unknown>; highly_connected_entities: unknown[]; components_preview: unknown[]; communities: unknown[];
  temporal_activity: unknown[]; indicators: IndicatorOut[]; terminology_notice: string;
  centrality?: Record<string, Record<string, number>> | null; centrality_explanations?: Record<string, string> | null;
  communities_detailed?: CommunityDetailOut[] | null; bridges_detailed?: BridgeDetailOut[] | null;
  temporal_indicators?: TemporalIndicatorOut[] | null; transaction_chains?: TransactionChainOut[] | null;
  relationship_strength?: RelationshipStrengthOut[] | null; indicators_enhanced?: StructuredIndicatorOut[] | null;
}

// M8A Investigation Engine — exact contracts from backend/schemas.py
export interface InvestigationSubgraphResponse {
  case_id?: string | null;
  root_entity: Record<string, unknown>;
  depth: number;
  entities: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  statistics: Record<string, unknown>;
  truncated: boolean;
  provenance: Record<string, unknown>[];
}
export interface InvestigationSubgraphRequest {
  case_id?: string | null;
  root_entity_id: string;
  depth: number;
  entity_types?: string[] | null;
  relationship_types?: string[] | null;
  max_nodes?: number;
  max_relationships?: number;
}
export interface InvestigationPathResponse {
  found: boolean;
  hop_count?: number | null;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  relationship_sequence: string[];
  provenance: Record<string, unknown>[];
}
export interface InvestigationPathRequest {
  source_id: string;
  target_id: string;
  max_depth: number;
  case_id?: string | null;
  relationship_types?: string[] | null;
}
export interface InvestigationEvidenceOut {
  evidence_id: string;
  evidence_type: string;
  description: string;
  entity_ids: string[];
  relationship_ids: string[];
  indicator_ids: string[];
  provenance: Record<string, unknown>[];
  created_at: string;
}
export interface InvestigationFindingOut {
  finding_id: string;
  finding_type: string;
  title: string;
  severity: string;
  explanation: string;
  entity_ids: string[];
  relationship_ids: string[];
  supporting_paths: InvestigationPathResponse[];
  indicators: StructuredIndicatorOut[];
  temporal_evidence: TemporalIndicatorOut[];
  transaction_evidence: TransactionChainOut[];
  centrality_context?: Record<string, unknown> | null;
  community_context?: Record<string, unknown> | null;
  evidence: InvestigationEvidenceOut[];
  provenance: Record<string, unknown>[];
  created_at: string;
}
export interface InvestigationFindingsResponse {
  case_id?: string | null;
  root_entity_id?: string | null;
  findings: InvestigationFindingOut[];
  count: number;
  provenance: Record<string, unknown>[];
}
export interface InvestigationSnapshotRequest {
  case_id?: string | null;
  root_entity_id: string;
  depth: number;
  entity_types?: string[] | null;
  relationship_types?: string[] | null;
  include_findings?: boolean;
  include_paths?: boolean;
  max_nodes?: number;
}
export interface InvestigationSnapshotResponse {
  snapshot_id: string;
  case_id?: string | null;
  root_entity: Record<string, unknown>;
  depth: number;
  entities: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  paths: InvestigationPathResponse[];
  findings: InvestigationFindingOut[];
  evidence: InvestigationEvidenceOut[];
  statistics: Record<string, unknown>;
  generated_at: string;
  provenance: Record<string, unknown>[];
}

// M9A Explainability & Audit — adapter-ready (no fake intelligence, backend is source)
export interface ProvenanceEntry {
  source: string;
  analysis_type?: string;
  timestamp?: string;
  parameters?: Record<string, unknown>;
  [k: string]: unknown;
}
export interface ExplanationResponse {
  target_id: string;
  target_type: string; // finding | entity | path | indicator | centrality | community | bridge | temporal | relationship
  title: string;
  summary: string;
  methodology: string;
  observations: string[];
  parameters: Record<string, unknown>;
  thresholds?: Record<string, unknown>;
  supporting_entities: string[];
  supporting_relationships: string[];
  supporting_evidence: InvestigationEvidenceOut[];
  provenance: ProvenanceEntry[];
  generated_at: string;
  limitations: string[];
  analysis_type: string;
}
export interface AuditEvent {
  audit_id: string;
  case_id?: string | null;
  root_entity_id?: string | null;
  event_type: string; // finding_generated | evidence_generated | path_computed | analysis_run | subgraph_generated
  analysis_type: string;
  target_id?: string | null;
  summary: string;
  timestamp: string;
  provenance: ProvenanceEntry[];
}
export interface AuditTrailResponse {
  case_id?: string | null;
  events: AuditEvent[];
  count: number;
  truncated: boolean;
  generated_at?: string;
}
