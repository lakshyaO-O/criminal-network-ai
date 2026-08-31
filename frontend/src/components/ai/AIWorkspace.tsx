import React, { useState, useEffect } from "react";
import { DATA_SOURCE } from "../../config";
import { LoadingState } from "../ui/LoadingState";
import { ErrorState } from "../ui/ErrorState";
import { EmptyState } from "../ui/EmptyState";
import { ProvenancePanel } from "../explainability/ProvenancePanel";
import { useAIStatus, useAIAnalysis, useAIEntityExtraction, useAIRelationshipExtraction } from "../../hooks/useAI";
import type { AIAnalysisOut, AIEntityMention } from "../../types";

const ANALYSIS_TYPES = [
  "network_summary",
  "centrality",
  "community",
  "bridge",
  "temporal",
  "transaction_chain",
  "indicator",
  "finding",
  "investigation_brief",
  "entity_brief",
  "network_brief",
] as const;

type AnalysisType = typeof ANALYSIS_TYPES[number];

interface Props {
  caseId: string | null;
  rootEntityId: string | null;
  onClear?: () => void;
}

function Section({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#262629] bg-[#0e0e10]/40 flex justify-between items-center gap-2">
        <span className="mono text-[11px] font-semibold tracking-wide text-[#d4d4d8]">{title}</span>
        {action}
      </div>
      <div className="px-3 py-3">{children}</div>
    </div>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">ANALYTICAL CONFIDENCE {pct}%</span>;
}

function ExtractionConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return <span className="mono text-[10px] px-1 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">EXTRACTION CONFIDENCE {pct}%</span>;
}

export function AIWorkspace({ caseId, rootEntityId }: Props) {
  const status = useAIStatus();
  const analysis = useAIAnalysis();
  const entityExt = useAIEntityExtraction();
  const relExt = useAIRelationshipExtraction();

  const [analysisType, setAnalysisType] = useState<AnalysisType>("network_summary");
  const [extractText, setExtractText] = useState("Rhea Verma works for Bluepeak Traders Pvt Ltd. +91-90-1234567");
  const [lastEntities, setLastEntities] = useState<AIEntityMention[] | null>(null);
  const [relText, setRelText] = useState("Rhea Verma works for Bluepeak Traders Pvt Ltd.");

  // Case/root context clearing — stale-result protection
  const analysisReset = analysis.reset;
  useEffect(() => {
    analysisReset();
  }, [caseId, rootEntityId, analysisReset]);

  const handleAnalyze = () => {
    if (DATA_SOURCE === "mock") return;
    analysis.analyze({
      analysis_type: analysisType,
      case_id: caseId ?? undefined,
      root_entity_id: rootEntityId ?? undefined,
    });
  };

  const handleExtractEntities = () => {
    if (!extractText.trim()) return;
    entityExt.extract({ text: extractText, source_id: caseId ?? undefined }).then(() => {});
  };

  // capture entities for relationship step when entity extraction succeeds
  useEffect(() => {
    if (entityExt.data?.entities) setLastEntities(entityExt.data.entities);
  }, [entityExt.data]);

  const handleExtractRelationships = () => {
    const ents = lastEntities;
    if (!ents || ents.length === 0) return;
    if (!relText.trim()) return;
    relExt.extract({ text: relText, entities: ents });
  };

  const isMock = DATA_SOURCE === "mock";
  const aiUnavailable = status.error && status.error.includes("mock mode");
  const statusAvailable = status.data?.available === true;

  return (
    <div className="flex flex-col gap-3 max-w-[1100px]">
      {/* Status */}
      <Section
        title="AI PROVIDER"
        action={
          <button
            onClick={() => status.refresh()}
            aria-label="Refresh AI status"
            className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]"
          >
            refresh
          </button>
        }
      >
        {isMock ? (
          <EmptyState title="AI unavailable in mock mode" hint="Set REACT_APP_DATA_SOURCE=api to enable real AI provider. Mock mode does not fabricate AI findings." />
        ) : status.loading ? (
          <LoadingState label="Checking AI status" />
        ) : status.error ? (
          <ErrorState title={statusAvailable ? "AI status" : "AI unavailable"} message={status.error} />
        ) : status.data ? (
          <div className="mono text-[11px] leading-relaxed">
            <div className="flex flex-wrap gap-1.5">
              <span className="px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#d4d4d8]">PROVIDER {status.data.provider}</span>
              <span className="px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">VERSION {status.data.provider_version}</span>
              <span className={`px-1.5 py-0.5 rounded-[6px] border ${statusAvailable ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200/80" : "border-amber-500/20 bg-amber-500/10 text-amber-200/80"}`}>
                {statusAvailable ? "AVAILABLE" : "UNAVAILABLE"}
              </span>
              <span className="px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">MODEL {status.data.model ?? "—"}</span>
              <span className="px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">
                REPRODUCIBLE {status.data.deterministic ? "YES" : "NO"}
              </span>
            </div>
            {status.data.description && <div className="mt-2 text-[11px] text-[#6b6b70] leading-snug">{status.data.description}</div>}
            <div className="mt-1 text-[10px] text-[#6b6b70]">AI assistance — analytical interpretation only; investigator review required; no guilt determination.</div>
          </div>
        ) : (
          <EmptyState title="No AI status" />
        )}
      </Section>

      {/* Analysis action */}
      <Section
        title="AI-ASSISTED ANALYSIS"
        action={<span className="mono text-[10px] text-[#6b6b70]">case {caseId ?? "—"} • root {rootEntityId ?? "—"}</span>}
      >
        {isMock ? (
          <EmptyState title="AI analysis unavailable in mock mode" hint="Real AI analysis requires API mode." />
        ) : (
          <>
            <div className="flex flex-wrap gap-2 items-center">
              <label htmlFor="ai-analysis-type" className="mono text-[10px] text-[#8a8a90]">
                ANALYSIS TYPE
              </label>
              <select
                id="ai-analysis-type"
                value={analysisType}
                onChange={(e) => setAnalysisType(e.target.value as AnalysisType)}
                className="mono text-[11px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]"
                aria-label="Select analysis type"
              >
                {ANALYSIS_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <button
                onClick={handleAnalyze}
                disabled={analysis.loading}
                className="text-[12px] font-medium px-3 py-1.5 rounded-[6px] bg-[#e8e8ea] text-[#0a0a0c] hover:bg-white disabled:opacity-50 focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]"
                aria-label="Run AI analysis"
              >
                {analysis.loading ? "Analyzing…" : "Run analysis"}
              </button>
              <button
                onClick={() => analysis.reset()}
                className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:text-[#d4d4d8]"
              >
                clear
              </button>
            </div>
            <div className="mono text-[10px] text-[#6b6b70] mt-2">Analysis preserves selected case/root; switching case or root clears previous result (M10B pattern).</div>
            <div className="mt-3">
              {analysis.loading && <LoadingState label="Running AI analysis" />}
              {analysis.error && <ErrorState title="AI analysis unavailable" message={analysis.error} />}
              {!analysis.loading && !analysis.error && !analysis.data && <EmptyState title="No AI analysis" hint="Select a type and run analysis. AI will summarize observed graph patterns and provide grounded interpretation." />}
              {analysis.data && <AIResultPanel analysis={analysis.data.analysis} provider={analysis.data.provider} model={analysis.data.model} />}
            </div>
          </>
        )}
      </Section>

      {/* Entity extraction */}
      <Section title="AI EXTRACT ENTITIES">
        {isMock ? (
          <EmptyState title="AI extraction unavailable in mock mode" hint="Use API mode for real extraction." />
        ) : (
          <>
            <div className="mono text-[10px] text-[#8a8a90] mb-1">Investigation/source text — treated as data, never instruction. Analytical result; not automatically persisted.</div>
            <textarea
              value={extractText}
              onChange={(e) => setExtractText(e.target.value)}
              placeholder="Enter investigation text..."
              rows={3}
              className="w-full mono text-[11px] bg-[#0e0e10] border border-[#262629] rounded-[8px] px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#3a3a3e] text-[#d4d4d8] resize-y"
              aria-label="Investigation text for entity extraction"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleExtractEntities}
                disabled={entityExt.loading || !extractText.trim()}
                className="mono text-[11px] px-3 py-1 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#d4d4d8] hover:bg-[#262629] disabled:opacity-50"
              >
                {entityExt.loading ? "Extracting…" : "AI extract entities"}
              </button>
              <button onClick={() => entityExt.reset()} className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">
                clear
              </button>
              <span className="mono text-[10px] text-[#6b6b70] self-center">Max 100k chars • bounded</span>
            </div>
            <div className="mt-3">
              {entityExt.loading && <LoadingState label="Extracting entities" />}
              {entityExt.error && <ErrorState title="Entity extraction unavailable" message={entityExt.error} />}
              {!entityExt.loading && !entityExt.error && !entityExt.data && <EmptyState title="No extraction" hint="Enter text and run AI extraction." />}
              {entityExt.data && (
                <div className="space-y-2">
                  <div className="mono text-[10px] text-[#6b6b70]">{entityExt.data.entity_count} entities • provider {entityExt.data.provider} • reproducible {String(entityExt.data.reproducibility?.deterministic)}</div>
                  <div className="overflow-auto border border-[#1e1e22] rounded-[6px]">
                    <table className="w-full mono text-[11px]">
                      <thead className="bg-[#0e0e10] text-[#8a8a90] border-b border-[#1e1e22]">
                        <tr>
                          <th className="text-left px-2 py-1 font-normal">VALUE</th>
                          <th className="text-left px-2 py-1 font-normal">TYPE</th>
                          <th className="text-left px-2 py-1 font-normal">CONF</th>
                          <th className="text-left px-2 py-1 font-normal">REVIEW</th>
                          <th className="text-left px-2 py-1 font-normal">METHOD</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e1e22]">
                        {entityExt.data.entities.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-2 py-4 text-center text-[#6b6b70]">
                              No entities extracted (empty result, not failure)
                            </td>
                          </tr>
                        ) : (
                          entityExt.data.entities.map((e, i) => (
                            <tr key={`${e.value}-${i}`} className="hover:bg-[#1e1e22]/30">
                              <td className="px-2 py-1 text-[#d4d4d8]">{e.value}</td>
                              <td className="px-2 py-1 text-[#8a8a90]">{e.canonical_type}</td>
                              <td className="px-2 py-1">
                                <ExtractionConfidenceBadge value={e.confidence} />
                              </td>
                              <td className="px-2 py-1">
                                {e.needs_review ? (
                                  <span className="mono text-[10px] px-1 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-200/80">NEEDS REVIEW</span>
                                ) : (
                                  <span className="mono text-[10px] text-[#6b6b70]">—</span>
                                )}
                              </td>
                              <td className="px-2 py-1 text-[#6b6b70] truncate max-w-[160px]" title={e.extraction_method}>
                                {e.extraction_method}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="mono text-[10px] text-[#6b6b70] border border-[#1e1e22] rounded-[6px] bg-[#0e0e10] px-2 py-1">Not automatically persisted • AI finding for investigator review</div>
                  {entityExt.data.provenance?.length > 0 && <ProvenancePanel provenance={entityExt.data.provenance as never} />}
                </div>
              )}
            </div>
          </>
        )}
      </Section>

      {/* Relationship extraction */}
      <Section title="AI EXTRACT RELATIONSHIPS">
        {isMock ? (
          <EmptyState title="AI extraction unavailable in mock mode" />
        ) : (
          <>
            <div className="mono text-[10px] text-[#8a8a90] mb-1">Uses entities from previous extraction + text (or manual). Preserves 11 canonical types; low confidence → needs review; not auto-written to graph.</div>
            <textarea
              value={relText}
              onChange={(e) => setRelText(e.target.value)}
              placeholder="Text context for relationships..."
              rows={2}
              className="w-full mono text-[11px] bg-[#0e0e10] border border-[#262629] rounded-[8px] px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#3a3a3e] text-[#d4d4d8] resize-y"
              aria-label="Text for relationship extraction"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleExtractRelationships}
                disabled={relExt.loading || !lastEntities || lastEntities.length === 0 || !relText.trim()}
                className="mono text-[11px] px-3 py-1 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#d4d4d8] hover:bg-[#262629] disabled:opacity-50"
                title={!lastEntities || lastEntities.length === 0 ? "Run entity extraction first" : undefined}
              >
                {relExt.loading ? "Extracting…" : "AI extract relationships"}
              </button>
              <button onClick={() => relExt.reset()} className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">clear</button>
            </div>
            {!lastEntities || lastEntities.length === 0 ? (
              <div className="mt-2 mono text-[10px] text-[#6b6b70]">Run entity extraction first to supply entities.</div>
            ) : null}
            <div className="mt-3">
              {relExt.loading && <LoadingState label="Extracting relationships" />}
              {relExt.error && <ErrorState title="Relationship extraction unavailable" message={relExt.error} />}
              {!relExt.loading && !relExt.error && !relExt.data && <EmptyState title="No relationship extraction" hint="Provide entities and text, then extract." />}
              {relExt.data && (
                <div className="space-y-2">
                  <div className="mono text-[10px] text-[#6b6b70]">{relExt.data.relationship_count} relationships • provider {relExt.data.provider}</div>
                  <div className="overflow-auto border border-[#1e1e22] rounded-[6px]">
                    <table className="w-full mono text-[11px]">
                      <thead className="bg-[#0e0e10] text-[#8a8a90] border-b border-[#1e1e22]">
                        <tr>
                          <th className="text-left px-2 py-1 font-normal">SOURCE → TARGET</th>
                          <th className="text-left px-2 py-1 font-normal">TYPE</th>
                          <th className="text-left px-2 py-1 font-normal">CONF</th>
                          <th className="text-left px-2 py-1 font-normal">REVIEW</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e1e22]">
                        {relExt.data.relationships.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="px-2 py-4 text-center text-[#6b6b70]">No relationships extracted (empty result, not failure)</td>
                          </tr>
                        ) : (
                          relExt.data.relationships.map((r, i) => {
                            const src = lastEntities?.[r.source_entity_index]?.value ?? `#${r.source_entity_index}`;
                            const tgt = lastEntities?.[r.target_entity_index]?.value ?? `#${r.target_entity_index}`;
                            return (
                              <tr key={`${r.relationship_type}-${i}`} className="hover:bg-[#1e1e22]/30">
                                <td className="px-2 py-1 text-[#d4d4d8]">{src} → {tgt}</td>
                                <td className="px-2 py-1 text-[#8a8a90]">{r.relationship_type}</td>
                                <td className="px-2 py-1"><ExtractionConfidenceBadge value={r.confidence} /></td>
                                <td className="px-2 py-1">{r.needs_review ? <span className="mono text-[10px] px-1 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-200/80">NEEDS REVIEW</span> : <span className="mono text-[10px] text-[#6b6b70]">—</span>}</td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="mono text-[10px] text-[#6b6b70]">Not automatically persisted • requires existing backend persistence workflow</div>
                </div>
              )}
            </div>
          </>
        )}
      </Section>

      <div className="mono text-[10px] text-[#6b6b70] border border-[#262629] rounded-[8px] bg-[#0e0e10]/30 px-3 py-2">AI audit integration: every AI request is logged as <code>ai_analysis_requested</code> in the audit trail (case_id / analysis_type / provider). View via Audit workspace — no frontend-fabricated events.</div>
    </div>
  );
}

function AIResultPanel({ analysis, provider, model }: { analysis: AIAnalysisOut; provider: string; model?: string | null }) {
  const a = analysis;
  return (
    <div className="border border-[#1e1e22] rounded-[8px] bg-[#0e0e10] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#1e1e22] bg-[#17171a] flex flex-wrap justify-between items-center gap-2">
        <span className="mono text-[11px] font-semibold text-[#d4d4d8]">{a.summary}</span>
        <span className="flex gap-1">
          <ConfidenceBadge value={a.confidence} />
          <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#6b6b70]">{a.analysis_type}</span>
        </span>
      </div>

      <div className="px-3 py-2 border-b border-[#1e1e22]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">OBSERVED</div>
        <ul className="list-disc list-inside mono text-[11px] text-[#a1a1aa] space-y-0.5">
          {a.observations.map((o, i) => (
            <li key={i}>{o}</li>
          ))}
        </ul>
      </div>

      <div className="px-3 py-2 border-b border-[#1e1e22]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">ANALYTICAL INTERPRETATION</div>
        <ul className="list-disc list-inside mono text-[11px] text-[#a1a1aa] space-y-0.5">
          {a.analytical_interpretation.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </div>

      {(a.supporting_entity_ids.length > 0 || a.supporting_relationship_ids.length > 0) && (
        <div className="px-3 py-2 border-b border-[#1e1e22]">
          <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">SUPPORTING</div>
          {a.supporting_entity_ids.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {a.supporting_entity_ids.slice(0, 8).map((id) => (
                <span key={id} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#17171a] border border-[#262629] text-[#8a8a90]">{id}</span>
              ))}
            </div>
          )}
          {a.supporting_relationship_ids.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {a.supporting_relationship_ids.slice(0, 8).map((id) => (
                <span key={id} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#17171a] border border-[#1e1e22] text-[#6b6b70]">{id}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="px-3 py-2 border-b border-[#1e1e22]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">METHODOLOGY</div>
        <div className="mono text-[11px] text-[#a1a1aa] leading-snug">{a.methodology}</div>
      </div>

      <div className="px-3 py-2 border-b border-[#1e1e22]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">LIMITATIONS</div>
        <div className="mono text-[11px] text-[#6b6b70] leading-snug">{a.limitations}</div>
      </div>

      <div className="px-3 py-2 border-b border-[#1e1e22]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">PROVENANCE</div>
        <ProvenancePanel provenance={a.provenance as never} />
      </div>

      <div className="px-3 py-2 border-b border-[#1e1e22] bg-[#0e0e10]/50">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">LINEAGE</div>
        <div className="mono text-[10px] text-[#6b6b70] break-all">
          <div>algorithm {String((a.lineage as Record<string, unknown>).algorithm ?? "—")}</div>
          <div>dataset {String((a.lineage as Record<string, unknown>).dataset_id ?? (a.lineage as Record<string, unknown>).dataset_id ?? "—")}</div>
          <div>deterministic {String((a.lineage as Record<string, unknown>).deterministic)}</div>
          <div>inputs {JSON.stringify((a.lineage as Record<string, unknown>).inputs ?? {}).slice(0, 180)}</div>
          <div>timestamp {String((a.lineage as Record<string, unknown>).timestamp ?? "—")}</div>
        </div>
      </div>

      <div className="px-3 py-2 bg-[#17171a]/50 border-t border-[#1e1e22]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">REPRODUCIBILITY</div>
        <div className="mono text-[10px] text-[#6b6b70]">
          <div>provider {provider} {model ? `• model ${model}` : ""} • version {(a.reproducibility as Record<string, string>).provider_version ?? "—"}</div>
          <div>input hash {(a.reproducibility as Record<string, string>).input_hash ?? "—"} • result {String((a.reproducibility as Record<string, string>).result_id ?? a.analysis_id)}</div>
          <div>deterministic {String((a.reproducibility as Record<string, unknown>).deterministic)}</div>
        </div>
      </div>
      {(a as unknown as { grounding_status?: string }).grounding_status && (
        <div className="px-3 py-2 bg-[#0e0e10] border-t border-[#1e1e22] flex justify-between items-center">
          <span className="mono text-[10px] text-[#8a8a90]">GROUNDING</span>
          <span className={`mono text-[10px] px-1.5 py-0.5 rounded-[6px] border ${(a as unknown as { grounding_status?: string }).grounding_status === "SUPPORTED" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200/80" : "border-amber-500/20 bg-amber-500/10 text-amber-200/80"}`}>
            {(a as unknown as { grounding_status?: string }).grounding_status}
          </span>
        </div>
      )}
    </div>
  );
}
