import { useEffect, useState, useRef } from "react";
import { DATA_SOURCE } from "../config";
import {
  getInvestigationSubgraph,
  getInvestigationFindings,
  getInvestigationEvidence
} from "../api/investigations";
import type {
  InvestigationSubgraphResponse,
  InvestigationFindingOut,
  InvestigationEvidenceOut
} from "../types";
import { ApiError } from "../api/client";

export function useInvestigationWorkspace() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [rootId, setRootId] = useState<string | null>(null);
  const [depth, setDepth] = useState<number>(2);
  const [subgraph, setSubgraph] = useState<InvestigationSubgraphResponse | null>(null);
  const [findings, setFindings] = useState<InvestigationFindingOut[]>([]);
  const [evidence, setEvidence] = useState<InvestigationEvidenceOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);

  const isActive = !!(caseId && rootId);

  function startInvestigation(cId: string, rId: string, d = 2) {
    setCaseId(cId); setRootId(rId); setDepth(d);
  }
  function clearInvestigation() {
    setCaseId(null); setRootId(null); setSubgraph(null); setFindings([]); setEvidence([]); setError(null); setLoading(false);
  }
  function setInvestigationDepth(d: number) {
    const clamped = Math.max(0, Math.min(6, Math.floor(d)));
    if (clamped !== d && (d < 0 || d > 6)) return;
    setDepth(clamped);
  }

  useEffect(() => {
    if (!caseId || !rootId) { setSubgraph(null); setFindings([]); setEvidence([]); setError(null); setLoading(false); return; }
    if (DATA_SOURCE === "mock") {
      setSubgraph({ case_id: caseId, root_entity: { entity_id: rootId }, depth, entities: [], relationships: [], statistics: {}, truncated: false, provenance: [] });
      setFindings([]); setEvidence([]); setError(null); setLoading(false);
      return;
    }
    const seq = ++seqRef.current;
    setLoading(true); setError(null);
    setSubgraph(null); setFindings([]); setEvidence([]);

    Promise.all([
      getInvestigationSubgraph({ root_entity_id: rootId, depth, case_id: caseId }),
      getInvestigationFindings({ case_id: caseId, root_entity_id: rootId, depth }),
      getInvestigationEvidence({ case_id: caseId, root_entity_id: rootId, depth })
    ]).then(([sg, findsRes, ev]) => {
      if (seq !== seqRef.current) return;
      setSubgraph(sg);
      setFindings(findsRes.findings);
      setEvidence(ev);
    }).catch((e: unknown) => {
      if (seq !== seqRef.current) return;
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
      setError(msg);
      setSubgraph(null);
    }).finally(()=> { if(seq===seqRef.current) setLoading(false); });

    return () => { /* seq guard */ };
  }, [caseId, rootId, depth]);

  return { caseId, rootId, depth, subgraph, findings, evidence, loading, error, isActive, startInvestigation, clearInvestigation, setDepth: setInvestigationDepth };
}
