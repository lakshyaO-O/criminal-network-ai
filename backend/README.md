# Backend

**Status: bootstrap layer only.** This Express service exists to prove the
deployment pipeline (Docker, ports, health checks). Per
`docs/architecture.md` (ADR-001), the target is a Python FastAPI service —
the core AI/graph/data workload is Python-native. Do not add domain logic
here; do not delete until the FastAPI migration is explicitly approved.

Responsibilities (bootstrap only):
- Health/deployment smoke checks (`/api/health`)
- Placeholder routes for frontend wiring

Tech: Node.js + TypeScript (bootstrap) → Python + FastAPI (target)