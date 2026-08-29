import sys, json
from fastapi.testclient import TestClient
sys.path.insert(0, 'C:/Users/nothing/criminal-network-ai')
sys.path.insert(0, 'C:/Users/nothing/criminal-network-ai/backend-python')

from app.main import create_app

app = create_app()
with TestClient(app) as client:
    # Test depth out of range (too low)
    r = client.get('/api/entities/person-00001/neighborhood?depth=0')
    print(f'depth=0: {r.status_code} {r.text[:100]}')
    
    r = client.get('/api/entities/person-00001/neighborhood?depth=7')
    print(f'depth=7: {r.status_code} {r.text[:100]}')
    
    # Test max_depth out of range
    r = client.get('/api/analysis/path?source_id=person-00001&target_id=person-00002&max_depth=7')
    print(f'max_depth=7: {r.status_code} {r.text[:100]}')
    
    r = client.get('/api/analysis/path?source_id=person-00001&target_id=person-00002&max_depth=0')
    print(f'max_depth=0: {r.status_code} {r.text[:100]}')
    
    # Test missing entity_id for centrality
    r = client.get('/api/explainability/centrality')
    print(f'centrality no entity_id: {r.status_code}')
    detail = r.json().get('detail', '') if r.status_code != 200 else ''
    print(f'  errors: {detail[:200]}')
    
    # Test invalid limit
    r = client.get('/api/audit/events?limit=0')
    print(f'limit=0: {r.status_code}')
    
    r = client.get('/api/audit/events?limit=101')
    print(f'limit=101: {r.status_code}')
    
    # Test negative offset
    r = client.get('/api/audit/events?offset=-1')
    print(f'offset=-1: {r.status_code}')