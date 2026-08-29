import sys
import os
# Add both directories to path
sys.path.insert(0, os.path.join(os.environ.get('HOME', 'C:\\Users\\nothing'), 'criminal-network-ai'))
sys.path.insert(0, os.path.join(os.environ.get('HOME', 'C:\\Users\\nothing'), 'criminal-network-ai', 'backend-python'))

from fastapi.testclient import TestClient
from app.main import create_app

app = create_app()
with TestClient(app) as client:
    # Test health endpoint - check persistence state
    r = client.get('/api/health')
    health = r.json()
    print('Health check:')
    print('  status:', health['status'])
    print('  database:', health['database'])
    print('  graph:', health['graph'])
    print()
    
    # Test entity lookup via API
    r = client.get('/api/entities/person-00001')
    print('Get entity person-00001:', r.status_code)
    if r.status_code == 200:
        print('  entity_type:', r.json().get('entity_type'))
    
    # Test case lookup
    r = client.get('/api/cases/case-00001')
    print('Get case case-00001:', r.status_code)
    if r.status_code == 200:
        print('  case_title:', r.json().get('title'))
    
    # Test neighborhood
    r = client.get('/api/entities/person-00001/neighborhood?depth=1')
    print('Get neighborhood:', r.status_code)
    if r.status_code == 200:
        nodes = r.json().get('nodes', [])
        edges = r.json().get('edges', [])
        print('  nodes:', len(nodes))
        print('  edges:', len(edges))