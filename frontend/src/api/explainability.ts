import { apiClient } from "./client";
import { DATA_SOURCE } from "../config";
import type { ExplanationResponse, ProvenanceEntry } from "../types";
import { getInvestigationFindings } from "./investigations";
import { getEntityAnalysis } from "./analysis";

// M9A Explainability adapter — M9A-ready, no fake intelligence.
// Attempts real M9 endpoint first; falls back to derived explanation from existing M8/M5 backend truth (clearly marked).

async function tryM9<T>(path: string, fallback: () => Promise<T>): Promise<T> {
  if (DATA_SOURCE === "mock") throw new Error("Explainability unavailable in mock mode");
  try {
    return await apiClient.get<T>(path);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    // If M9 not yet published (404), use derived fallback for development; otherwise propagate error (no silent downgrade)
    if (msg.includes("404") || msg.includes("Not Found")) {
      return fallback();
    }
    throw e;
  }
}

export async function getFindingExplanation(findingId: string, caseId?: string | null, rootId?: string | null): Promise<ExplanationResponse> {
  // Try M9: GET /api/explainability/findings/{findingId}
  return tryM9<ExplanationResponse>(`/explainability/findings/${encodeURIComponent(findingId)}`, async () => {
    // Derived fallback: fetch findings and map matching one
    const res = await getInvestigationFindings({ case_id: caseId ?? undefined, root_entity_id: rootId ?? undefined, depth: 2 });
    const f = res.findings.find(x => x.finding_id === findingId);
    if (!f) throw new Error(`Finding ${findingId} not found`);
    return {
      target_id: f.finding_id,
      target_type: "finding",
      title: f.title,
      summary: f.explanation.slice(0, 160),
      methodology: f.provenance?.[0]?.analysis_type ? String(f.provenance[0].analysis_type) : f.finding_type,
      observations: [f.explanation, `Severity ${f.severity}`, `Entities ${f.entity_ids.join(", ") || "—"}`],
      parameters: { finding_type: f.finding_type, severity: f.severity, entity_ids: f.entity_ids },
      thresholds: {},
      supporting_entities: f.entity_ids,
      supporting_relationships: f.relationship_ids,
      supporting_evidence: f.evidence,
      provenance: (f.provenance as ProvenanceEntry[]) || [],
      generated_at: f.created_at,
      limitations: [
        "Analytical signal, not proof of guilt or criminality",
        "Dependent on available graph data and deterministic thresholds",
        f.provenance?.length ? "" : "Provenance limited to current subgraph scope"
      ].filter(Boolean),
      analysis_type: f.finding_type
    };
  });
}

export async function getEntityExplanation(entityId: string): Promise<ExplanationResponse> {
  return tryM9<ExplanationResponse>(`/explainability/entities/${encodeURIComponent(entityId)}`, async () => {
    const data = await getEntityAnalysis(entityId);
    const c = data.centrality;
    return {
      target_id: entityId,
      target_type: "entity",
      title: `Entity ${entityId} — analytical context`,
      summary: `Degree ${c.degree.toFixed(3)}, betweenness ${c.betweenness.toFixed(3)}, closeness ${c.closeness.toFixed(3)}, pagerank ${c.pagerank.toFixed(3)}`,
      methodology: "NetworkX degree/betweenness/closeness/pagerank (damping 0.85) on current graph snapshot",
      observations: [
        `Degree centrality ${c.degree.toFixed(3)} — direct connections relative to graph size`,
        `Betweenness ${c.betweenness.toFixed(3)} — frequency on shortest paths`,
        `Closeness ${c.closeness.toFixed(3)} — inverse average distance`,
        `PageRank ${c.pagerank.toFixed(3)} — link-analysis score`
      ],
      parameters: { entity_id: entityId, metrics: c },
      thresholds: {},
      supporting_entities: [entityId, ...(data.neighborhood?.nodes?.map((n: Record<string,unknown>)=> String((n as Record<string,string>).entity_id)).filter((id:string)=> id!==entityId) || [])].slice(0,6),
      supporting_relationships: [],
      supporting_evidence: [],
      provenance: [{ source: "graph_repo", analysis_type: "centrality", timestamp: new Date().toISOString() }],
      generated_at: new Date().toISOString(),
      limitations: ["Deterministic graph metrics on current snapshot; truncated network affects scores", "Not a risk or criminality score"],
      analysis_type: "entity_centrality"
    };
  });
}

export async function getPathExplanation(sourceId: string, targetId: string, caseId?: string | null): Promise<ExplanationResponse> {
  return tryM9<ExplanationResponse>(`/explainability/paths?source_id=${encodeURIComponent(sourceId)}&target_id=${encodeURIComponent(targetId)}${caseId?`&case_id=${encodeURIComponent(caseId)}`:""}`, async () => {
    const { getInvestigationPaths } = await import("./investigations");
    const p = await getInvestigationPaths({ source_id: sourceId, target_id: targetId, max_depth: 6, case_id: caseId ?? undefined });
    return {
      target_id: `${sourceId}→${targetId}`,
      target_type: "path",
      title: `Path ${sourceId} → ${targetId}`,
      summary: p.found ? `${p.hop_count} hops via ${p.relationship_sequence.join(" → ")}` : "No path within max depth",
      methodology: "BFS shortest path on investigation subgraph (filtered, bounded, deterministic)",
      observations: p.found ? [`Hop count ${p.hop_count}`, `Nodes ${p.nodes.map((n: Record<string,unknown>)=> String((n as Record<string,string>).entity_id)).join(" → ")}`] : ["No path found within depth 6"],
      parameters: { source_id: sourceId, target_id: targetId, max_depth: 6, case_id: caseId },
      thresholds: { max_depth: 6 },
      supporting_entities: p.nodes.map((n: Record<string,unknown>)=> String((n as Record<string,string>).entity_id)),
      supporting_relationships: p.relationship_sequence,
      supporting_evidence: [],
      provenance: p.provenance as ProvenanceEntry[],
      generated_at: new Date().toISOString(),
      limitations: ["Path existence depends on current graph scope and filters", "Deterministic BFS, not weighted"],
      analysis_type: "path"
    };
  });
}

export async function getCentralityExplanation(): Promise<ExplanationResponse> {
  return tryM9<ExplanationResponse>("/explainability/centrality", async () => {
    const { getCentrality } = await import("./analysis");
    const c = await getCentrality();
    return {
      target_id: "centrality",
      target_type: "centrality",
      title: "Centrality — methodology",
      summary: "Degree, betweenness, closeness, PageRank on current graph",
      methodology: (c.explanations.degree || "") + " " + (c.explanations.betweenness || ""),
      observations: Object.entries(c.centrality.degree).slice(0,3).map(([id, v])=> `${id} degree ${Number(v).toFixed(3)}`),
      parameters: { metrics: Object.keys(c.centrality) },
      thresholds: {},
      supporting_entities: Object.keys(c.centrality.degree).slice(0,5),
      supporting_relationships: [],
      supporting_evidence: [],
      provenance: [{ source: "network_analysis", analysis_type: "centrality", timestamp: new Date().toISOString() }],
      generated_at: new Date().toISOString(),
      limitations: ["Scores are analytical, not guilt; truncated graph affects PageRank"],
      analysis_type: "centrality"
    };
  });
}
