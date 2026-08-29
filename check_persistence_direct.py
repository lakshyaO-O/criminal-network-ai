import sys
import os
sys.path.insert(0, os.path.join(os.environ.get('HOME', 'C:\\Users\\nothing'), 'criminal-network-ai'))
sys.path.insert(0, os.path.join(os.environ.get('HOME', 'C:\\Users\\nothing'), 'criminal-network-ai', 'backend-python'))

from app.config import settings
from ai.persistence.postgres import PostgresPersistence

# Test persistence operations
print('Testing persistence with in-memory fallback')
print('Data dir:', settings.data_dir)
print()

# Test that the persistence can do basic operations
from ai.persistence.postgres import PostgresPersistence as PG

# Check if we can instantiate (will use in-memory if no DB)
try:
    pers = PG()
    print('Persistence instantiated successfully')
    print('Type:', type(pers))
except Exception as e:
    print('Error instantiating persistence:', e)