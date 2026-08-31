"""Pydantic request/response schemas for the FastAPI API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# --- Health ----------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "criminal-network-analysis"
    version: str = "1.0.0"
    neo4j_connected: Optional[bool] = None  # legacy, kept for backwards compat
    database: Optional[Dict[str, str]] = None  # e.g. {"postgresql": "connected"|"disconnected"|"in_memory"}
    graph: Optional[Dict[str, str]] = None  # e.g. {"neo4j": "connected"|"disconnected"}


# --- Extraction endpoints ---------------------------------------------------

class ExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)
    source_id: Optional[str] = None
    use_spacy: bool = False  # optional spaCy enrichment


class ExtractedEntityOut(BaseModel):
    text: str
    entity_type: str
    start_offset: int
    end_offset: int
    normalized_value: Optional[str] = None
    entity_id: Optional[str] = None
    confidence: Optional[float] = None
    extraction_method: str
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ExtractionResponse(BaseModel):
    source_id: Optional[str]
    entities: List[ExtractedEntityOut]
    entity_count: int


class RelationshipExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)
    source_id: Optional[str] = None
    entities: List[ExtractedEntityOut] = []  # optional pre-extracted
    structured_records: List[Dict[str, Any]] = []


class RelationshipOut(BaseModel):
    relationship_id: str
    source: Dict[str, Any]
    target: Dict[str, Any]
    relationship_type: str
    timestamp: Optional[str] = None
    confidence: float
    extraction_method: str
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class RelationshipExtractionResponse(BaseModel):
    source_id: Optional[str]
    relationships: List[RelationshipOut]
    relationship_count: int


# --- Investigation pipeline -------------------------------------------------

class PipelineRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)
    source_id: Optional[str] = None
    structured_records: List[Dict[str, Any]] = []
    use_spacy: bool = False
    persist: bool = True
    sync_graph: bool = True


class ResolutionCandidateOut(BaseModel):
    candidate_entity_id: str
    match_method: str
    confidence: float
    supporting_fields: List[str] = []
    status: str


class PipelineResponse(BaseModel):
    source_id: Optional[str]
    preprocessed_text: str
    entities: List[ExtractedEntityOut]
    resolutions: Dict[str, List[ResolutionCandidateOut]]
    relationships: List[RelationshipOut]
    validation_errors: List[str] = []
    persisted: Dict[str, int] = {}
    graph_sync: Dict[str, int] = {}


# --- Entity lookups ---------------------------------------------------------

class EntityOut(BaseModel):
    entity_id: str
    entity_type: str
    full_name: Optional[str] = None
    name: Optional[str] = None
    number: Optional[str] = None
    registration_number: Optional[str] = None
    account_number: Optional[str] = None
    case_number: Optional[str] = None
    fir_number: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = {}


class EntityRelationshipsOut(BaseModel):
    entity_id: str
    relationships: List[RelationshipOut]


class NeighborhoodOut(BaseModel):
    start_entity_id: str
    depth: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class ShortestPathOut(BaseModel):
    found: bool
    length: Optional[int]
    entities: List[str]
    relationships: List[str]


# --- Cases ------------------------------------------------------------------

class CaseOut(BaseModel):
    case_id: str
    case_number: str
    title: str
    description: str
    case_type: str
    status: str
    assigned_to: Optional[str] = None
    opened_at: Optional[str] = None
    metadata: Dict[str, Any] = {}


class NetworkOut(BaseModel):
    case_id: str
    entities: List[EntityOut]
    relationships: List[RelationshipOut]
    statistics: Dict[str, Any]


# --- Analysis ----------------------------------------------------------------

class IndicatorOut(BaseModel):
    entity_id: str
    indicator: str
    reason: str
    evidence: List[str] = []


# Milestone 5: structured indicator with severity and explainability
class StructuredIndicatorOut(BaseModel):
    indicator_id: str
    indicator_type: str
    severity: str  # LOW | MEDIUM | HIGH (analytical signal, not criminality)
    entity_ids: List[str] = []
    relationship_ids: List[str] = []
    score: float
    explanation: str
    evidence: List[str] = []
    created_at: str


class CentralityResponse(BaseModel):
    centrality: Dict[str, Dict[str, float]]
    explanations: Dict[str, str]
    top_entities: List[Dict[str, Any]]


class CommunityDetailOut(BaseModel):
    community_id: str
    members: List[str]
    size: int
    internal_edges: int
    density: float


class BridgeDetailOut(BaseModel):
    entity_id: str
    entity_type: str
    metric: str
    score: float
    explanation: str
    evidence: List[str] = []


class TemporalIndicatorOut(BaseModel):
    indicator_type: str
    time_window: str
    entity_ids: List[str] = []
    observed_count: int
    baseline: Dict[str, Any]
    explanation: str
    evidence: List[str] = []


class TransactionChainOut(BaseModel):
    chain_id: str
    source_account: str
    intermediate_accounts: List[str] = []
    destination_account: str
    hop_count: int
    transaction_count: int
    evidence: List[str] = []
    explanation: str


class RelationshipStrengthOut(BaseModel):
    relationship_id: str
    relationship_type: str
    source_id: str
    target_id: str
    interaction_strength: float
    factors: Dict[str, Any]
    explanation: str


class IndicatorsResponse(BaseModel):
    indicators: List[StructuredIndicatorOut]
    count: int


class AnalysisResponse(BaseModel):
    counts: Dict[str, Any]
    entity_type_counts: Dict[str, int]
    relationship_type_counts: Dict[str, int]
    degree_statistics: Dict[str, Any]
    highly_connected_entities: List[Dict[str, Any]]
    components_preview: List[Dict[str, Any]]
    communities: List[Dict[str, Any]]
    temporal_activity: List[Dict[str, Any]]
    indicators: List[IndicatorOut]
    terminology_notice: str
    # Milestone 5 enriched (optional for backward compat)
    centrality: Optional[Dict[str, Dict[str, float]]] = None
    centrality_explanations: Optional[Dict[str, str]] = None
    communities_detailed: Optional[List[CommunityDetailOut]] = None
    bridges_detailed: Optional[List[BridgeDetailOut]] = None
    temporal_indicators: Optional[List[TemporalIndicatorOut]] = None
    transaction_chains: Optional[List[TransactionChainOut]] = None
    relationship_strength: Optional[List[RelationshipStrengthOut]] = None
    indicators_enhanced: Optional[List[StructuredIndicatorOut]] = None


# --- Investigation (Milestone 8A) ------------------------------------------------

# Limits (documented, deterministic)
INVESTIGATION_MAX_DEPTH = 6
INVESTIGATION_MAX_NODES = 200
INVESTIGATION_MAX_RELATIONSHIPS = 400
INVESTIGATION_MAX_PATHS = 20
INVESTIGATION_MAX_FINDINGS = 20


class InvestigationSubgraphRequest(BaseModel):
    case_id: Optional[str] = Field(None, description="Case context; if provided, subgraph is intersected with case network")
    root_entity_id: str = Field(..., description="Root entity for N-hop expansion")
    depth: int = Field(1, ge=0, le=6, description="Hop depth 0..6 (0 = root only)")
    entity_types: Optional[List[str]] = Field(None, description="Filter to entity types (canonical 12)")
    relationship_types: Optional[List[str]] = Field(None, description="Filter to relationship types (canonical 11)")
    max_nodes: int = Field(200, ge=1, le=500, description="Maximum entities returned (truncation)")
    max_relationships: int = Field(400, ge=1, le=1000, description="Maximum relationships returned")


class InvestigationSubgraphResponse(BaseModel):
    case_id: Optional[str] = None
    root_entity: Dict[str, Any]
    depth: int
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    truncated: bool = False
    provenance: List[Dict[str, Any]] = []


class InvestigationPathRequest(BaseModel):
    source_id: str
    target_id: str
    max_depth: int = Field(6, ge=1, le=6)
    case_id: Optional[str] = None
    relationship_types: Optional[List[str]] = None


class InvestigationPathResponse(BaseModel):
    found: bool
    hop_count: Optional[int] = None
    nodes: List[Dict[str, Any]] = []  # each: {entity_id, entity_type, properties}
    edges: List[Dict[str, Any]] = []  # each: {relationship_id, relationship_type, source_id, target_id, provenance}
    relationship_sequence: List[str] = []
    provenance: List[Dict[str, Any]] = []


class InvestigationEvidenceOut(BaseModel):
    evidence_id: str
    evidence_type: str  # e.g., "relationship", "path", "temporal", "community", "centrality"
    description: str
    entity_ids: List[str] = []
    relationship_ids: List[str] = []
    indicator_ids: List[str] = []
    provenance: List[Dict[str, Any]] = []
    created_at: str


class InvestigationFindingOut(BaseModel):
    finding_id: str
    finding_type: str  # e.g., "bridge_entity", "temporal_burst", "transaction_chain"
    title: str
    severity: str = Field(..., pattern="^(LOW|MEDIUM|HIGH)$")
    explanation: str  # what, why, which entities
    entity_ids: List[str] = []
    relationship_ids: List[str] = []
    supporting_paths: List[InvestigationPathResponse] = []
    indicators: List[StructuredIndicatorOut] = []
    temporal_evidence: List[TemporalIndicatorOut] = []
    transaction_evidence: List[TransactionChainOut] = []
    centrality_context: Optional[Dict[str, Any]] = None
    community_context: Optional[Dict[str, Any]] = None
    evidence: List[InvestigationEvidenceOut] = []
    provenance: List[Dict[str, Any]] = []
    created_at: str


class InvestigationFindingsResponse(BaseModel):
    case_id: Optional[str] = None
    root_entity_id: Optional[str] = None
    findings: List[InvestigationFindingOut]
    count: int
    provenance: List[Dict[str, Any]] = []


class InvestigationSnapshotRequest(BaseModel):
    case_id: Optional[str] = None
    root_entity_id: str
    depth: int = Field(2, ge=0, le=6)
    entity_types: Optional[List[str]] = None
    relationship_types: Optional[List[str]] = None
    include_findings: bool = True
    include_paths: bool = True
    max_nodes: int = Field(200, ge=1, le=500)


class InvestigationSnapshotResponse(BaseModel):
    snapshot_id: str
    case_id: Optional[str] = None
    root_entity: Dict[str, Any]
    depth: int
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    paths: List[InvestigationPathResponse] = []
    findings: List[InvestigationFindingOut] = []
    evidence: List[InvestigationEvidenceOut] = []
    statistics: Dict[str, Any]
    generated_at: str
    provenance: List[Dict[str, Any]] = []


# --- Explainability (Milestone 9A) ------------------------------------------------

class ExplanationOut(BaseModel):
    explanation_id: str
    analysis_type: str
    summary: str
    methodology: str
    observations: List[str] = []
    contributing_entities: List[str] = []
    contributing_relationships: List[str] = []
    supporting_evidence: List[str] = []
    parameters: Dict[str, Any] = {}
    thresholds: Dict[str, Any] = {}
    limitations: str
    provenance: List[Dict[str, Any]] = []
    generated_at: str
    lineage: Dict[str, Any] = {}
    reproducibility: Dict[str, Any] = {}


class LineageOut(BaseModel):
    analysis_type: str
    algorithm: str
    parameters: Dict[str, Any] = {}
    inputs: Dict[str, Any] = {}
    observations: List[str] = []
    output_summary: str
    dataset_id: str
    deterministic: bool
    timestamp: str


class AuditEventOut(BaseModel):
    audit_id: str
    event_type: str
    timestamp: str
    case_id: Optional[str] = None
    entity_id: Optional[str] = None
    root_entity_id: Optional[str] = None
    analysis_type: Optional[str] = None
    object_id: Optional[str] = None
    parameters: Dict[str, Any] = {}
    provenance: List[Dict[str, Any]] = []
    status: str


class AuditQueryResponse(BaseModel):
    events: List[AuditEventOut]
    count: int
    total: int
    limit: int
    offset: int


# --- AI Assistant (Milestone 12A) ---------------------------------------------

# Neutral terminology only. Confidence = analytical confidence, not p(guilt).

class AIStatusResponse(BaseModel):
    provider: str
    provider_version: str
    available: bool
    model: Optional[str] = None
    deterministic: bool = True
    description: Optional[str] = None
    input_max_len: Optional[int] = None


class AIExtractEntitiesRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000, description="Investigation text — treated as data, never instruction")
    source_id: Optional[str] = Field(None, max_length=200)
    provider: Optional[str] = Field(None, description="Override provider: deterministic|local; default from env")


class AIExtractEntitiesResponse(BaseModel):
    source_id: Optional[str] = None
    provider: str
    provider_version: str
    model: Optional[str] = None
    entities: List[Dict[str, Any]]  # AIEntityMention dicts (canonical_type, value, start, end, confidence, extraction_method, provenance, needs_review)
    entity_count: int
    provenance: List[Dict[str, Any]] = []
    lineage: Dict[str, Any] = {}
    reproducibility: Dict[str, Any] = {}


class AIExtractRelationshipsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)
    source_id: Optional[str] = Field(None, max_length=200)
    entities: List[Dict[str, Any]] = Field(default_factory=list, max_length=500, description="AIEntityMention list from previous call or manual")
    structured_records: List[Dict[str, Any]] = Field(default_factory=list, max_length=200)
    provider: Optional[str] = None


class AIExtractRelationshipsResponse(BaseModel):
    source_id: Optional[str] = None
    provider: str
    provider_version: str
    model: Optional[str] = None
    relationships: List[Dict[str, Any]]  # AIRelationshipMention dicts
    relationship_count: int
    provenance: List[Dict[str, Any]] = []
    lineage: Dict[str, Any] = {}
    reproducibility: Dict[str, Any] = {}


class AIAnalyzeRequest(BaseModel):
    analysis_type: str = Field("network_summary", description="network_summary|centrality|community|bridge|temporal|transaction_chain|indicator|finding|investigation_brief|entity_brief|network_brief")
    text: Optional[str] = Field(None, max_length=100000, description="Optional free-form context — sanitized, not executed")
    case_id: Optional[str] = Field(None, max_length=50)
    root_entity_id: Optional[str] = Field(None, max_length=50)
    graph_snapshot: Optional[Dict[str, Any]] = Field(None, description="Optional explicit snapshot; if omitted, derived from current graph")
    provider: Optional[str] = None


class AIAnalysisOut(BaseModel):
    analysis_id: str
    analysis_type: str
    summary: str
    observations: List[str]
    analytical_interpretation: List[str] = Field(..., description="Grounded interpretation, not guilt")
    supporting_entity_ids: List[str] = []
    supporting_relationship_ids: List[str] = []
    supporting_evidence_ids: List[str] = []
    confidence: float = Field(..., ge=0.0, le=1.0, description="Analytical interpretation confidence, NOT guilt probability")
    methodology: str
    limitations: str
    provenance: List[Dict[str, Any]] = []
    lineage: Dict[str, Any] = {}
    reproducibility: Dict[str, Any] = {}
    grounding_status: str = Field("SUPPORTED", description="SUPPORTED or NEEDS_REVIEW from grounding validator")
    grounding_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed grounding checks")


class AIAnalyzeResponse(BaseModel):
    provider: str
    provider_version: str
    model: Optional[str] = None
    analysis: AIAnalysisOut
    provenance: List[Dict[str, Any]] = []
    lineage: Dict[str, Any] = {}
    reproducibility: Dict[str, Any] = {}