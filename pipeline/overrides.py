#!/usr/bin/env python3
"""Read the HR team's transfers (Unsuitable page -> dashboard) from Supabase into pipeline/app/overrides.json.

The page stores one document per transferred person in table `docs`, collection "overrides":
  id   = candidate key, "S:<10-digit phone>" (sheet applicant) or "A:<HR-app key>"
  data = {ro: [roles], lv: "check"|"medium"|"strong", reason, hr (who), at (when), ...}
v3/build.py applies them: a resume Claude rated "hide" is shown on the dashboard with these roles and level.

Env: SUPABASE_URL, SUPABASE_KEY (same as runs.py).
Without them, or when Supabase cannot be reached, the file already in the repo is kept, so transfers
applied earlier never disappear because of a network hiccup. This script never fails the sync.
"""
import json, os, sys
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'pipeline', 'app', 'overrides.json')
URL = os.environ.get('SUPABASE_URL', '').strip().rstrip('/')
if URL.endswith('/rest/v1'):          # accept the URL with or without /rest/v1
    URL = URL[:-len('/rest/v1')]
KEY = os.environ.get('SUPABASE_KEY', '')
LEVELS = ('strong', 'medium', 'check')
PAGE = 1000


def fetch_all():
    rows, offset = [], 0
    while True:
        r = requests.get(URL + '/rest/v1/docs',
                         params={'collection': 'eq.overrides', 'select': 'id,data,updated_at', 'order': 'id',
                                 'limit': PAGE, 'offset': offset},
                         headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY}, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError('Supabase %s: %s' % (r.status_code, r.text[:200]))
        part = r.json()
        if not isinstance(part, list):
            raise RuntimeError('unexpected reply: %s' % str(part)[:200])
        rows += part
        if len(part) < PAGE:
            return rows
        offset += PAGE


def clean(doc):
    """Keep only what build.py needs; None when the document cannot be applied."""
    d = doc.get('data') or {}
    if not isinstance(d, dict):
        return None
    ro = [str(x) for x in (d.get('ro') or []) if x]
    if not ro:
        return None
    lv = d.get('lv') if d.get('lv') in LEVELS else 'check'
    return {'ro': ro, 'lv': lv, 'reason': str(d.get('reason') or '')[:600], 'hr': str(d.get('hr') or '')[:80],
            'at': str(d.get('at') or doc.get('updated_at') or '')}


def load_current():
    try:
        return json.load(open(OUT, encoding='utf-8'))
    except Exception:
        return {}


def main():
    before = load_current()
    if not URL or not KEY:
        print('SUPABASE_URL / SUPABASE_KEY not set - keeping overrides.json as it is (%d transfers)' % len(before))
        return
    try:
        docs = fetch_all()
    except Exception as e:
        print('could not read transfers from Supabase - keeping overrides.json as it is (%d transfers): %s'
              % (len(before), str(e)[:200]))
        return
    out = {}
    for doc in docs:
        c = clean(doc)
        if c and doc.get('id'):
            out[str(doc['id'])] = c
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    added, removed = sorted(set(out) - set(before)), sorted(set(before) - set(out))
    print(json.dumps({'transfers': len(out), 'added': len(added), 'removed': len(removed),
                      'added_keys': added[:20], 'removed_keys': removed[:20]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
