import sys
sys.path.insert(0, 'C:/Users/nothing/criminal-network-ai')
sys.path.insert(0, 'C:/Users/nothing/criminal-network-ai/backend-python')

from fastapi.testclient import TestClient
from app.main import create_app

app = create_app()
with TestClient(app) as client:
    endpoints = [
        ('/api/analysis', 'Analysis'),
        ('/api/analysis/centrality', 'Centrality'),
        ('/api/analysis/communities', 'Communities'),
        ('/api/analysis/bridges', 'Bridges'),
        ('/api/analysis/temporal', 'Temporal'),
        ('/api/analysis/transaction-chains', 'Transaction Chains'),
        ('/api/analysis/relationship-strength', 'Relationship Strength'),
        ('/api/analysis/indicators', 'Indicators'),
        ('/api/analysis/path?source_id=person-00001&target_id=person-00002', 'Path'),
        ('/api/analysis/entities/person-00001', 'Entity'),
        ('/api/analysis/entities/person-00001/centrality', 'Entity Centrality'),
        ('/api/analysis/entities/person-00001/neighborhood', 'Entity Neighborhood'),
        ('/api/investigations/subgraph?root_entity_id=person-00001&depth=1', 'Subgraph'),
        ('/api/investigations/paths?source_id=person-00001&target_id=person-00002', 'Paths'),
        ('/api/investigations/findings?root_entity_id=person-00001&depth=1', 'Findings'),
        ('/api/investigations/evidence?root_entity_id=person-00001&depth=1', 'Evidence'),
        ('/api/explainability/centrality?entity_id=person-00001', 'Centrality Explain'),
        ('/api/explainability/entities/person-00001', 'Entity Explain'),
        ('/api/explainability/bridges/person-00001', 'Bridge Explain'),
        ('/api/explainability/temporal', 'Temporal Explain'),
        ('/api/explainability/transaction-chains', 'Chain Explain'),
        ('/api/explainability/indicators/ind-bridge-person-00001', 'Indicator Explain'),
        ('/api/explainability/relationship-strength/rel-00001', 'Strength Explain'),
        ('/api/explainability/findings/finding-a1b2c3', 'Finding Explain 404'),
        ('/api/explainability/entities/person-00001', 'Entity Explain Path'),
        ('/api/explainability/centrality/person-00001', 'Centrality Path'),
        ('/api/explainability/centrality', 'Centrality Query'),
        ('/api/explainability/communities', 'Communities Explain'),
        ('/api/explainability/communities/person-00001', 'Community Entity'),
        ('/api/explainability/bridges/person-00001', 'Bridge Explain'),
        ('/api/explainability/temporal', 'Temporal Explain'),
        ('/api/explainability/transaction-chains', 'Chain Explain'),
        ('/api/explainability/indicators/ind-bridge-person-00001', 'Indicator Explain'),
        ('/api/explainability/relationship-strength/rel-00001', 'Strength Explain'),
        ('/api/explainability/findings/finding-a1b2c3', 'Finding Explain 404'),
        ('/api/explainability/entities/person-00001', 'Entity Explain Path'),
        ('/api/explainability/centrality/person-00001', 'Centrality Path'),
        ('/api/explainability/centrality', 'Centrality Query'),
        ('/api/explainability/communities', 'Communities Explain'),
        ('/api/explainability/communities/person-00001', 'Community Entity'),
        ('/api/explainability/bridges/person-00001', 'Bridge Explain'),
        ('/api/explainability/temporal', 'Temporal Explain'),
        ('/api/explainability/transaction-chains', 'Chain Explain'),
        ('/api/explainability/indicators/ind-bridge-person-00001', 'Indicator Explain'),
        ('/api/explainability/relationship-strength/rel-00001', 'Strength Explain'),
        ('/api/explainability/findings/finding-a1b2c3', 'Finding Explain 404'),
        ('/api/explainability/entities/person-00001', 'Entity Explain Path'),
        ('/api/explainability/centrality/person-00001', 'Centrality Path'),
        ('/api/explainability/centrality', 'Centrality Query'),
        ('/api/explainability/communities', 'Communities Explain'),
        ('/api/explainability/communities/person-00001', 'Community Entity'),
        ('/api/explainability/bridges/person-00001', 'Bridge Explain'),
        ('/api/explainability/temporal', 'Temporal Explain'),
        ('/api/explainability/transaction-chains', 'Chain Explain'),
        ('/api/explainability/indicators/ind-bridge-person-00001', 'Indicator Explain'),
        ('/api/explainability/relationship-strength/rel-00001', 'Strength Explain'),
        ('/api/explainability/findings/finding-a1b2c3', 'Finding Explain 404'),
        ('/api/explainability/entities/person-00001', 'Entity Explain Path'),
        ('/api/explainability/centrality/person-00001', 'Centrality Path'),
        ('/api/explainability/centrality', 'Centrality Query'),
        ('/api/explainability/communities', 'Communities Explain'),
        ('/api/explainability/communities/person-00001', 'Community Entity'),
        ('/api/explainability/bridges/person-00001', 'Bridge Explain'),
        ('/api/explainability/temporal', 'Temporal Explain'),
        ('/api/explainability/transaction-chains', 'Chain Explain'),
        ('/api/explainability/indicators/ind-bridge-person-00001', 'Indicator Explain'),
        ('/api/explainability/relationship-strength/rel-00001', 'Strength Explain'),
        ('/api/explainability/findings/finding-a1b2c3', 'Finding Explain 404'),
        ('/api/explainability/entities/person-00001', 'Entity Explain Path'),
        ('/api/explainability/centrality/person-00001', 'Centrality Path'),
        ('/api/explainability/centrality', 'Centrality Query'),
        ('/api/explainability/communities', 'Communities Explain'),
        ('/api/explainability/communities/person-00001', 'Community Entity'),
        ('/api/explainability/bridges/person-00001', 'Bridge Explain'),
        ('/api/explainability/temporal', 'Temporal Explain'),
        ('/api/explainability/transaction-chains', 'Chain Explain'),
        ('/api/explainability/indicators/ind-bridge-person-00001', 'Indicator Explain'),
        ('/api/explainability/relationship-strength/rel-00001', 'Strength Explain'),
        ('/api/explainability/findings/finding-a1b2c3', 'Finding Explain 404'),
        ('/api/audit/events?limit=5', 'Audit Events'),
    ]
    
    for path, name in endpoints:
        r = client.get(path)
        status = r.status_code
        ok = status == 200
        print(f'{name}: {"OK" if ok else "FAIL"} ({status})')
        if not ok:
            print(f'  Error: {r.text[:200]}')