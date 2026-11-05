#!/usr/bin/env python3
"""hr-tracker positions (v1.12): write public/tracker.json for the Reports tab.
Run after naukri_export.py (step 7 of the sync; local/serve.py runs it too).

The HR Recruitment Tracker (https://hr-p1.onrender.com/) keeps its positions in a Supabase project that the tracker
page reads directly with its public anon key. This script reads the same two tables (positions, recruiters) so the
Reports tab can limit its "By district" table to the states that have an open position.

Env (all optional):
  TRACKER_URL           the tracker page, default https://hr-p1.onrender.com/ (the anon key is read from its HTML)
  TRACKER_SUPABASE_URL  default https://xzwbjblfpjijfcasjykp.supabase.co
  TRACKER_ANON_KEY      skip reading the page and use this key

If the tracker cannot be reached the last saved copy (pipeline/sheets/tracker_latest.json) is used, so the sync
never fails because of it. Output: {"at": "YYYY-MM-DD HH:MM:SS", "source": "...", "cols": [...], "rows": [[...]], "open": n}
with status "open" (not closed, not temporarily closed), "temp" or "closed".
"""
import json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'pipeline', 'sheets', 'tracker_latest.json')
OUT = os.path.join(ROOT, 'public', 'tracker.json')
PAGE = (os.environ.get('TRACKER_URL') or 'https://hr-p1.onrender.com/').strip()
SB = (os.environ.get('TRACKER_SUPABASE_URL') or 'https://xzwbjblfpjijfcasjykp.supabase.co').strip().rstrip('/')
COLS = ['id', 'st', 'city', 'dept', 'desig', 'seats', 'rec', 'open', 'prio', 'status']


def get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'hr-screening-sync'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8')


def anon_key():
    k = (os.environ.get('TRACKER_ANON_KEY') or '').strip()
    if k:
        return k
    m = re.search(r'SUPABASE_ANON_KEY\s*=\s*"([^"]+)"', get(PAGE, timeout=90))
    if not m:
        raise RuntimeError('anon key not found in the tracker page')
    return m.group(1)


def table(name, key, select='*'):
    h = {'apikey': key, 'Authorization': 'Bearer ' + key, 'User-Agent': 'hr-screening-sync'}
    rows, off, page = [], 0, 1000
    while True:
        part = json.loads(get('%s/rest/v1/%s?select=%s&limit=%d&offset=%d' % (SB, name, select, page, off), h))
        rows += part
        if len(part) < page:
            return rows
        off += page


def main():
    raw, source = None, ''
    try:
        key = anon_key()
        raw = {'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'positions': table('positions', key),
               'recruiters': table('recruiters', key, 'id,name')}
        os.makedirs(os.path.dirname(SRC), exist_ok=True)
        with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(raw, f, ensure_ascii=False)
        source = 'hr-tracker (live)'
    except Exception as e:                                   # network, key or table trouble: keep the last copy
        print('tracker: could not read the live data:', e, file=sys.stderr)
        if os.path.exists(SRC):
            raw = json.load(open(SRC, encoding='utf-8'))
            source = 'saved copy from ' + raw.get('at', '?')
    rows = []
    if raw:
        rec = {r.get('id'): r.get('name') or '' for r in raw.get('recruiters', [])}
        for p in raw.get('positions', []):
            status = 'closed' if p.get('closed') else 'temp' if p.get('temp_closed') else 'open'
            rows.append([p.get('id') or '', (p.get('state') or '').strip(), (p.get('city') or '').strip(),
                         (p.get('department') or '').strip(), (p.get('designation') or '').strip(),
                         int(p.get('quantity') or 1), rec.get(p.get('recruiter_id'), ''), p.get('open_date') or '',
                         bool(p.get('priority')), status])
        rows.sort(key=lambda r: (r[1], r[4], r[2]))
    data = {'at': (raw or {}).get('at', ''), 'source': source or 'none (tracker not reachable, no saved copy)',
            'cols': COLS, 'rows': rows, 'open': sum(1 for r in rows if r[9] == 'open')}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('public/tracker.json', len(rows), 'positions,', data['open'], 'open,', len(text), 'bytes; source:', data['source'])


if __name__ == '__main__':
    main()
