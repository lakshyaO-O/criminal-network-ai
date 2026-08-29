import { apiClient } from "./client";
import type { CaseOut } from "../types";
import { DATA_SOURCE } from "../config";
import { cases as mockCases } from "../data/mockData";

export async function getCase(caseId: string): Promise<CaseOut> {
  if (DATA_SOURCE === "mock") {
    const c = mockCases.find(x => x.id === caseId);
    if (!c) throw new Error(`Case ${caseId} not found`);
    return { case_id: c.id, case_number: c.number, title: c.title, description: c.title, case_type: "investigation", status: c.status, metadata: {} };
  }
  return apiClient.get<CaseOut>(`/cases/${encodeURIComponent(caseId)}`);
}
export async function listCasesMock(): Promise<CaseOut[]> {
  return mockCases.map(c => ({ case_id: c.id, case_number: c.number, title: c.title, description: c.title, case_type: "investigation", status: c.status, metadata: {} }));
}
