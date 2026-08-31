import { apiClient } from "./client";
import type { AnalysisResponse } from "../types";

export interface CentralityData { centrality: Record<string, Record<string, number>>; explanations: Record<string, string>; }
export interface CommunitiesData { communities: { community_id: string; members: string[]; size: number; internal_edges: number; density: number }[]; count: number; }
export interface BridgesData { bridges: { entity_id: string; entity_type: string; metric: string; score: number; explanation: string; evidence: string[] }[]; count: number; }
export interface TemporalData { temporal_indicators: { indicator_type: string; time_window: string; entity_ids: string[]; observed_count: number; baseline: { mean: number; std: number; threshold: number }; explanation: string; evidence: string[] }[]; count: number; }
export interface TransactionChainsData { transaction_chains: { chain_id: string; source_account: string; intermediate_accounts: string[]; destination_account: string; hop_count: number; evidence: string[]; explanation: string }[]; count: number; }
export interface RelationshipStrengthData { relationship_strength: { relationship_id: string; relationship_type: string; source_id: string; target_id: string; interaction_strength: number; factors: Record<string, unknown>; explanation: string }[]; count: number; }
export interface IndicatorsData { indicators: { indicator_id: string; indicator_type: string; severity: string; entity_ids: string[]; relationship_ids: string[]; score: number; explanation: string; evidence: string[]; created_at: string }[]; count: number; }
export interface PathData { found: boolean; length?: number | null; entities: string[]; relationships: string[]; }

export function getCentrality() { return apiClient.get<CentralityData>("/analysis/centrality"); }
export function getCommunities() { return apiClient.get<CommunitiesData>("/analysis/communities"); }
export function getBridges() { return apiClient.get<BridgesData>("/analysis/bridges"); }
export function getTemporal() { return apiClient.get<TemporalData>("/analysis/temporal"); }
export function getTransactionChains() { return apiClient.get<TransactionChainsData>("/analysis/transaction-chains"); }
export function getRelationshipStrength() { return apiClient.get<RelationshipStrengthData>("/analysis/relationship-strength"); }
export function getIndicators() { return apiClient.get<IndicatorsData>("/analysis/indicators"); }
export function getPath(source_id: string, target_id: string, max_depth = 6) { return apiClient.get<PathData>(`/analysis/path?source_id=${encodeURIComponent(source_id)}&target_id=${encodeURIComponent(target_id)}&max_depth=${max_depth}`); }
export function getAnalysis(caseId?: string) { return apiClient.get<AnalysisResponse>(caseId ? `/analysis/${encodeURIComponent(caseId)}` : "/analysis", { timeoutMs: 15000 }); }
export function getEntityAnalysis(entityId: string) { return apiClient.get<{ entity_id: string; centrality: Record<string, number>; centrality_explanations: Record<string, string>; neighborhood: { nodes: { entity_id: string; depth: number }[]; edges: { from: string; to: string; relationship_type: string }[] }; indicators: IndicatorsData["indicators"] }>(`/analysis/entities/${encodeURIComponent(entityId)}`, { timeoutMs: 15000 }); }
export function getEntityCentrality(entityId: string) { return apiClient.get<{ entity_id: string; centrality: Record<string, number>; explanations: Record<string, string> }>(`/analysis/entities/${encodeURIComponent(entityId)}/centrality`); }
