import { Entity, Relationship, TimelineEvent, Alert, CaseItem } from "../types";

export const entities: Entity[] = [
  { id: "PER-00042", type: "Person", displayName: "Rhea Verma", confidence: 0.92, relationshipCount: 18, sourceCount: 7, associatedCases: ["CASE-00003", "CASE-00001"], lastObserved: "2026-08-21 19:42:11", metadata: { nationality: "IN", dob: "1985-03-12" } },
  { id: "PER-00017", type: "Person", displayName: "Arjun Mehta", confidence: 0.88, relationshipCount: 12, sourceCount: 5, associatedCases: ["CASE-00003"], lastObserved: "2026-08-20 14:05:33", metadata: { nationality: "IN", dob: "1988-07-22" } },
  { id: "PER-00008", type: "Person", displayName: "Kavita Rao", confidence: 0.85, relationshipCount: 9, sourceCount: 4, associatedCases: ["CASE-00003"], lastObserved: "2026-08-19 11:30:00", metadata: { nationality: "IN" } },
  { id: "PER-00031", type: "Person", displayName: "Vikram Singh", confidence: 0.81, relationshipCount: 7, sourceCount: 3, associatedCases: ["CASE-00001"], lastObserved: "2026-08-18 09:12:44", metadata: {} },
  { id: "ORG-00004", type: "Organization", displayName: "Bluepeak Traders Pvt Ltd", confidence: 0.95, relationshipCount: 14, sourceCount: 6, associatedCases: ["CASE-00003"], lastObserved: "2026-08-21 18:00:00", metadata: { sector: "Trading" } },
  { id: "ORG-00007", type: "Organization", displayName: "Northline Logistics", confidence: 0.89, relationshipCount: 10, sourceCount: 4, associatedCases: ["CASE-00003"], lastObserved: "2026-08-20 16:22:10", metadata: { sector: "Logistics" } },
  { id: "PHONE-00017", type: "Phone", displayName: "+91-90123-45678", confidence: 0.96, relationshipCount: 6, sourceCount: 3, associatedCases: ["CASE-00003"], lastObserved: "2026-08-21 19:40:00", metadata: { carrier: "Airtel" } },
  { id: "PHONE-00022", type: "Phone", displayName: "+91-98100-11223", confidence: 0.94, relationshipCount: 5, sourceCount: 2, associatedCases: ["CASE-00003"], lastObserved: "2026-08-20 10:11:22", metadata: { carrier: "Jio" } },
  { id: "VEH-00005", type: "Vehicle", displayName: "MH-02-AB-1234", confidence: 0.87, relationshipCount: 4, sourceCount: 2, associatedCases: ["CASE-00003"], lastObserved: "2026-08-19 08:45:00", metadata: { model: "Bolero White" } },
  { id: "VEH-00009", type: "Vehicle", displayName: "DL-04-CA-5678", confidence: 0.83, relationshipCount: 3, sourceCount: 2, associatedCases: ["CASE-00001"], lastObserved: "2026-08-18 17:30:00", metadata: { model: "Swift Grey" } },
  { id: "LOC-00012", type: "Location", displayName: "Sector 12 Market, Delhi", confidence: 0.90, relationshipCount: 11, sourceCount: 5, associatedCases: ["CASE-00003"], lastObserved: "2026-08-21 12:00:00", metadata: { city: "Delhi" } },
  { id: "LOC-00019", type: "Location", displayName: "Warehouse Unit B, Nhava Sheva", confidence: 0.88, relationshipCount: 8, sourceCount: 4, associatedCases: ["CASE-00003"], lastObserved: "2026-08-20 22:10:00", metadata: { city: "Mumbai" } },
  { id: "ACC-00014", type: "Account", displayName: "ACC-9012-XXXX-4412", confidence: 0.91, relationshipCount: 9, sourceCount: 4, associatedCases: ["CASE-00003"], lastObserved: "2026-08-21 15:30:00", metadata: { bank: "SBI" } },
  { id: "ACC-00031", type: "Account", displayName: "ACC-3321-XXXX-9981", confidence: 0.89, relationshipCount: 7, sourceCount: 3, associatedCases: ["CASE-00003"], lastObserved: "2026-08-20 11:00:00", metadata: { bank: "HDFC" } },
];

export const relationships: Relationship[] = [
  { id: "REL-00001", source: "PER-00042", target: "ORG-00004", type: "ASSOCIATED_WITH", confidence: 0.82, timestamp: "2026-08-20T10:00:00Z", sourceId: "DOC-001" },
  { id: "REL-00002", source: "PER-00042", target: "PHONE-00017", type: "OWNS", confidence: 0.93, timestamp: "2026-08-21T19:40:00Z", sourceId: "DOC-002" },
  { id: "REL-00003", source: "PER-00042", target: "LOC-00012", type: "LOCATED_AT", confidence: 0.76, timestamp: "2026-08-21T12:00:00Z", sourceId: "DOC-003" },
  { id: "REL-00004", source: "PER-00042", target: "ACC-00014", type: "OWNS", confidence: 0.84, timestamp: "2026-08-21T15:30:00Z", sourceId: "DOC-004" },
  { id: "REL-00005", source: "PER-00042", target: "PER-00017", type: "CALLED", confidence: 0.79, timestamp: "2026-08-20T14:05:00Z", sourceId: "DOC-005" },
  { id: "REL-00006", source: "PER-00017", target: "ORG-00004", type: "ASSOCIATED_WITH", confidence: 0.74, timestamp: "2026-08-19T11:30:00Z", sourceId: "DOC-006" },
  { id: "REL-00007", source: "PER-00017", target: "PHONE-00022", type: "OWNS", confidence: 0.90, timestamp: "2026-08-20T10:11:00Z", sourceId: "DOC-007" },
  { id: "REL-00008", source: "PER-00017", target: "VEH-00005", type: "USED", confidence: 0.68, timestamp: "2026-08-19T08:45:00Z", sourceId: "DOC-008" },
  { id: "REL-00009", source: "ORG-00004", target: "LOC-00012", type: "LOCATED_AT", confidence: 0.81, timestamp: "2026-08-20T16:22:00Z", sourceId: "DOC-009" },
  { id: "REL-00010", source: "ORG-00004", target: "ORG-00007", type: "ASSOCIATED_WITH", confidence: 0.72, timestamp: "2026-08-20T16:00:00Z", sourceId: "DOC-010" },
  { id: "REL-00011", source: "PER-00008", target: "LOC-00019", type: "LOCATED_AT", confidence: 0.77, timestamp: "2026-08-20T22:10:00Z", sourceId: "DOC-011" },
  { id: "REL-00012", source: "PER-00008", target: "PER-00042", type: "ASSOCIATED_WITH", confidence: 0.75, timestamp: "2026-08-19T11:30:00Z", sourceId: "DOC-012" },
  { id: "REL-00013", source: "ACC-00014", target: "ACC-00031", type: "TRANSFERRED_TO", confidence: 0.88, timestamp: "2026-08-21T15:30:00Z", sourceId: "TXN-001" },
  { id: "REL-00014", source: "VEH-00005", target: "LOC-00012", type: "LOCATED_AT", confidence: 0.70, timestamp: "2026-08-19T08:45:00Z", sourceId: "DOC-013" },
  { id: "REL-00015", source: "VEH-00005", target: "LOC-00019", type: "LOCATED_AT", confidence: 0.69, timestamp: "2026-08-20T22:10:00Z", sourceId: "DOC-014" },
  { id: "REL-00016", source: "PER-00031", target: "VEH-00009", type: "OWNS", confidence: 0.80, timestamp: "2026-08-18T17:30:00Z", sourceId: "DOC-015" },
  { id: "REL-00017", source: "PER-00031", target: "LOC-00012", type: "LOCATED_AT", confidence: 0.66, timestamp: "2026-08-18T09:12:00Z", sourceId: "DOC-016" },
  { id: "REL-00018", source: "PHONE-00017", target: "PHONE-00022", type: "CALLED", confidence: 0.78, timestamp: "2026-08-21T19:42:00Z", sourceId: "DOC-017" },
  { id: "REL-00019", source: "ORG-00007", target: "LOC-00019", type: "LOCATED_AT", confidence: 0.83, timestamp: "2026-08-20T22:00:00Z", sourceId: "DOC-018" },
  { id: "REL-00020", source: "PER-00008", target: "PHONE-00022", type: "CALLED", confidence: 0.71, timestamp: "2026-08-20T10:15:00Z", sourceId: "DOC-019" },
];

export const timelineEvents: TimelineEvent[] = [
  { id: "EVT-00001", timestamp: "2026-08-21 19:42:11", eventType: "Communication", entities: ["PER-00042", "PHONE-00017", "PHONE-00022"], source: "DOC-017", confidence: 0.78, description: "Call record: PER-00042 — PHONE-00017 → PHONE-00022" },
  { id: "EVT-00002", timestamp: "2026-08-21 15:30:00", eventType: "Transaction", entities: ["ACC-00014", "ACC-00031"], source: "TXN-001", confidence: 0.88, description: "Transfer ACC-00014 → ACC-00031 (INR 50,000)" },
  { id: "EVT-00003", timestamp: "2026-08-21 12:00:00", eventType: "Movement", entities: ["PER-00042", "LOC-00012"], source: "DOC-003", confidence: 0.76, description: "Observed at Sector 12 Market" },
  { id: "EVT-00004", timestamp: "2026-08-20 22:10:00", eventType: "Movement", entities: ["PER-00008", "VEH-00005", "LOC-00019"], source: "DOC-011", confidence: 0.77, description: "Vehicle VEH-00005 at Warehouse Unit B" },
  { id: "EVT-00005", timestamp: "2026-08-20 14:05:33", eventType: "Communication", entities: ["PER-00042", "PER-00017"], source: "DOC-005", confidence: 0.79, description: "Call between PER-00042 and PER-00017" },
  { id: "EVT-00006", timestamp: "2026-08-20 10:11:22", eventType: "Association", entities: ["PER-00017", "PHONE-00022"], source: "DOC-007", confidence: 0.90, description: "Phone ownership verified" },
  { id: "EVT-00007", timestamp: "2026-08-19 11:30:00", eventType: "Association", entities: ["PER-00008", "PER-00042"], source: "DOC-012", confidence: 0.75, description: "Co-occurrence in DOC-012" },
  { id: "EVT-00008", timestamp: "2026-08-19 08:45:00", eventType: "Movement", entities: ["VEH-00005", "LOC-00012"], source: "DOC-013", confidence: 0.70, description: "Vehicle sighting at Sector 12" },
];

export const alerts: Alert[] = [
  { id: "ALT-0001", entityId: "PER-00042", indicator: "high_network_centrality", title: "Unusual communication burst", reason: "PER-00042 shows 18 observed relationships across 4 entity types — higher than baseline (avg 6.2)", evidence: ["REL-00001", "REL-00002", "REL-00005"], severity: "medium", timestamp: "2026-08-21 19:45:00" },
  { id: "ALT-0002", entityId: "ACC-00014", indicator: "bridge_candidate", title: "Repeated cross-location interaction", reason: "ACC-00014 links two account clusters via TRANSFERRED_TO; removal would disconnect components", evidence: ["REL-00013"], severity: "high", timestamp: "2026-08-21 15:35:00" },
  { id: "ALT-0003", entityId: "VEH-00005", indicator: "bridge_candidate", title: "Unexpected transaction pattern", reason: "VEH-00005 observed at two distant locations within 14h (LOC-00012 ↔ LOC-00019)", evidence: ["REL-00014", "REL-00015"], severity: "medium", timestamp: "2026-08-20 22:15:00" },
  { id: "ALT-0004", entityId: "PHONE-00022", indicator: "high_network_centrality", title: "Newly observed relationship", reason: "PHONE-00022 appears with 3 entities in last 24h — new link PER-00008 → PHONE-00022", evidence: ["REL-00020"], severity: "low", timestamp: "2026-08-20 10:20:00" },
];

export const cases: CaseItem[] = [
  { id: "CASE-00003", number: "SYN-CASE-2024-003", title: "Inquiry 003 — Cross-entity association review", status: "open", entityCount: 12 },
  { id: "CASE-00001", number: "SYN-CASE-2024-001", title: "Inquiry 001 — Financial irregularity", status: "under_review", entityCount: 6 },
];

export const allSearchItems = [...entities.map(e => ({ id: e.id, label: `${e.id} — ${e.displayName}`, type: e.type })), ...cases.map(c => ({ id: c.id, label: `${c.id} — ${c.title}`, type: "Case" as const })), ...relationships.map(r => ({ id: r.id, label: `${r.id} ${r.type}`, type: "Relationship" as const }))];
