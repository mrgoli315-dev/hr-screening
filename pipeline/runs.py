#!/usr/bin/env python3
"""Write the sync status the page shows ("Last automatic update ...", the Sync button progress).
Stored in Supabase table `docs`, collection "runs" — same shape the Claude page used.

  python pipeline/runs.py started
  python pipeline/runs.py done      (reads work/new.json, work/rate.json, work/merge.json)
  python pipeline/runs.py failed <step> <message>

Env: SUPABASE_URL, SUPABASE_KEY (anon or service key), RUN_ID (same id for the whole run)
"""
import datetime, json, os, sys
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_KEY', '')
RUN_ID = os.environ.get('RUN_ID') or datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S')
STAMP = os.path.join(ROOT, 'work', 'run_started_at.txt')


def now():
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')


def put(data):
    if not URL or not KEY:
        print('SUPABASE_URL / SUPABASE_KEY not set - status not written')
        return
    r = requests.post(URL + '/rest/v1/docs',
                      headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json',
                               'Prefer': 'resolution=merge-duplicates,return=minimal'},
                      json=[{'collection': 'runs', 'id': RUN_ID, 'data': data, 'updated_at': now()}], timeout=30)
    if r.status_code >= 300:
        print('status write failed', r.status_code, r.text[:300])


def load(name):
    p = os.path.join(ROOT, 'work', name)
    try:
        return json.load(open(p))
    except Exception:
        return {}


def started_at():
    try:
        return open(STAMP).read().strip()
    except Exception:
        return now()


cmd = sys.argv[1] if len(sys.argv) > 1 else ''
if cmd == 'started':
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    at = now()
    open(STAMP, 'w').write(at)
    put({'at': at, 'status': 'started'})
elif cmd == 'done':
    n, r, m = load('new.json'), load('rate.json'), load('merge.json')
    put({'at': started_at(), 'status': 'done', 'new_bde': n.get('new_bde', 0), 'new_bdm': n.get('new_bdm', 0),
         'new_mba': n.get('new_mba', 0), 'read': r.get('rated', 0), 'waiting': m.get('still_waiting', 0)})
elif cmd == 'failed':
    step = sys.argv[2] if len(sys.argv) > 2 else '?'
    msg = ' '.join(sys.argv[3:]) or 'see the GitHub Actions log'
    put({'at': started_at(), 'status': 'failed', 'step': step, 'error': msg[:300]})
else:
    print(__doc__)
