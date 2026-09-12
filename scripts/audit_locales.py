# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

def audit():
    base_dir = Path(__file__).resolve().parent.parent
    loc_dir = base_dir / 'client' / 'locales'
    ar_file = loc_dir / 'ar.json'
    en_file = loc_dir / 'en.json'

    if not ar_file.is_file() or not en_file.is_file():
        print('Locale files missing!')
        sys.exit(1)

    ar_data = json.loads(ar_file.read_text(encoding='utf-8'))
    en_data = json.loads(en_file.read_text(encoding='utf-8'))

    ar_keys = set(ar_data.keys())
    en_keys = set(en_data.keys())

    missing_in_en = ar_keys - en_keys
    missing_in_ar = en_keys - ar_keys

    print(f'Total AR keys: {len(ar_keys)}')
    print(f'Total EN keys: {len(en_keys)}')
    print(f'Keys in AR but missing in EN: {len(missing_in_en)}')
    for k in sorted(missing_in_en):
        print(f'  [AR -> MISSING IN EN]: {k}')
    print(f'Keys in EN but missing in AR: {len(missing_in_ar)}')
    for k in sorted(missing_in_ar):
        print(f'  [EN -> MISSING IN AR]: {k}')

if __name__ == '__main__':
    audit()
