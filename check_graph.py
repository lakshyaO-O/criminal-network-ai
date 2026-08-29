import sys, os
sys.path.insert(0, os.path.join(os.environ.get('HOME', 'C:\\Users\\nothing'), 'criminal-network-ai'))
sys.path.insert(0, os.path.join(os.environ.get('HOME', 'C:\\Users\\nothing'), 'criminal-network-ai', 'backend-python'))

from fastapi.testclient import TestClient
from app.main import create_app

app = create_app()
with TestClient(app) as client:
    def safe_get(path, **params):
        try:
            r = client.get(path, **params)
            return r.status_code, r.text[:100] if r.text else ''
        except Exception as e:
            return 'ERROR', str(e)[:100]
    
    # Test neighborhood at various depths
    print('=== Neighborhood depth tests ===')
    status, txt = safe_get('/api/entities/person-00001/neighborhood?depth=1')
    print('depth=1: {} {}'.format(status, txt))
    status, txt = safe_get('/api/entities/person-00001/neighborhood?depth=6')
    print('depth=6: {} {}'.format(status, txt))
    status, txt = safe_get('/api/entities/person-00001/neighborhood?depth=7')
    print('depth=7: {} {}'.format(status, txt))
    
    # Test nonexistent entity returns 404
    status, txt = safe_get('/api/entities/nonexistent-99999/neighborhood?depth=1')
    print('nonexistent entity: {} {}'.format(status, txt))
    
    # Test shortest path with non-existent entities
    print()
    print('=== Path tests ===')
    status, txt = safe_get('/api/analysis/path?source_id=person-00001&target_id=nonexistent&max_depth=3')
    print('path nonexistent target: {} {}'.format(status, txt))
    status, txt = safe_get('/api/analysis/path?source_id=nonexistent&target_id=person-00002&max_depth=3')
    print('path nonexistent source: {} {}'.format(status, txt))
    
    # Test bridges endpoint
    print()
    print('=== Bridges test ===')
    r = client.get('/api/analysis/bridges')
    print('bridges: {} count={}'.format(r.status_code, len(r.json().get('bridges', []))))
    
    # Test communities
    print()
    print('=== Communities test ===')
    r = client.get('/api/analysis/communities')
    print('communities: {} count={}'.format(r.status_code, len(r.json().get('communities', []))))
    
    # Test temporal
    print()
    print('=== Temporal test ===')
    r = client.get('/api/analysis/temporal')
    print('temporal: {} count={}'.format(r.status_code, len(r.json().get('temporal_indicators', []))))
    
    # Test indicators
    print()
    print('=== Indicators test ===')
    r = client.get('/api/analysis/indicators')
    print('indicators: {} count={}'.format(r.status_code, len(r.json().get('indicators', []))))
    
    # Test relationship strength
    print()
    print('=== Relationship strength test ===')
    r = client.get('/api/analysis/relationship-strength')
    print('relationship-strength: {} count={}'.format(r.status_code, len(r.json().get('relationship_strength', []))))