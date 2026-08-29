import sys
sys.path.insert(0, 'C:/Users/nothing/criminal-network-ai')
sys.path.insert(0, 'C:/Users/nothing/criminal-network-ai/backend-python')

import json
from pathlib import Path

data_dir = Path('data/synthetic')
for f in sorted(data_dir.glob('*.json')):
    if f.name.startswith('_'): continue
    data = json.load(f.open())
    if isinstance(data, list) and data:
        first = data[0]
        eid = first.get('entity_id', first.get(f"{f.stem[:-1]}_id"))
        print(f'{f.stem}: {len(data)} items, first ID: {eid}')
    else:
        print(f'{f.stem}: {type(data)}')