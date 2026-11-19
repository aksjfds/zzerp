"""Physical material identity independent of plan snapshot node IDs."""

import json
from hashlib import sha256


def material_stock_key(context, material_id: str) -> str:
    parts = context['parts']
    if material_id in parts:
        identity = ['part', parts[material_id]['part_no']]
    else:
        identity = ['assembly', sorted((parts[part]['part_no'], units)
                    for part, units in context['requirements'][material_id].items())]
    canonical = json.dumps(identity, ensure_ascii=False, separators=(',', ':'))
    return sha256(canonical.encode('utf-8')).hexdigest()
