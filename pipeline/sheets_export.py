#!/usr/bin/env python3
"""All applications (v1.8): write every Google Sheet row to public/applications.json for the page's
"All applications" tab. Run after publish.py (step 7 of the sync; local/serve.py runs it too).

Sources, in this order of preference:
  work/bde_rows.json, work/mba_rows.json    the full sheets as fetch.py downloaded them this run (edits included)
  pipeline/sheets/*_latest.json             the saved copies, when running locally without a fetch
The BDM sheet is no longer fetched (fetch.py reads BDE + MBA), so it always comes from the saved copy.

Output: {"cols": [...], "rows": [[...], ...], "latest": "YYYY-MM-DD HH:MM:SS", "counts": {"BDE": n, ...}}
Rows are arrays in the order of "cols" (small file; the page turns them into objects). Nothing is deduplicated:
one row per form submission. The output is deterministic, so a run with no sheet change commits nothing.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work')
SHEETS = os.path.join(ROOT, 'pipeline', 'sheets')
OUT = os.path.join(ROOT, 'public', 'applications.json')

COLS = ['src', 'ts', 'n', 'ph', 'em', 'st', 'fd', 'yrs', 'tm', 'ctc', 'ectc', 'tv', 'nt', 'fmcg', 'fs', 'res', 'stat', 'resu']
LINK = re.compile(r'https?://\S+')


def rows_from(work_name, cache_name):
    p = os.path.join(WORK, work_name) if work_name else ''
    if p and os.path.exists(p):
        rows = json.load(open(p, encoding='utf-8'))
        return (rows if isinstance(rows, list) else rows.get('values', [])), 'work/' + work_name
    p = os.path.join(SHEETS, cache_name)
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        return (d.get('values', []) if isinstance(d, dict) else d), 'pipeline/sheets/' + cache_name
    return [], None


def cell(r, i):
    return (r[i] if i < len(r) else '') or ''


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def ts_key(s):
    """'10/16/2026 9:59:20' -> '2026-10-16 09:59:20' (sorts as text). Anything else is returned as typed."""
    m = re.match(r'\s*(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$', s or '')
    if not m:
        return clean(s)
    mo, d, y, hh, mm, ss = m.groups()
    return '%s-%02d-%02d %02d:%s:%s' % (y, int(mo), int(d), int(hh or 0), mm or '00', ss or '00')


def phone10(s):
    d = re.sub(r'\D', '', s or '')
    if len(d) == 12 and d.startswith('91'): d = d[2:]
    if len(d) == 11 and d.startswith('0'): d = d[1:]
    return d


def link(s):
    m = LINK.search(s or '')
    return m.group(0) if m else ''


def is_header(r):
    return not re.match(r'\s*\d{1,2}/\d{1,2}/\d{4}', cell(r, 0)) and cell(r, 0).strip().lower() in ('timestamp', '', 'date')


def first_text(cells):
    for c in cells:
        if clean(c): return clean(c)
    return ''


def bde_row(r):
    """The BDE sheet has no header and two layouts: rows before Oct 5 2026 have the resume link in column G and the
    interview status in columns I/J; form rows since then have the form answers in G..M and the link in N."""
    base = ['BDE', ts_key(cell(r, 0)), clean(cell(r, 1)), phone10(cell(r, 2)), clean(cell(r, 3)), clean(cell(r, 4)), clean(cell(r, 5))]
    if len(r) > 13 or (len(r) > 10 and not link(cell(r, 6))):
        return base + [clean(cell(r, 6)), '', clean(cell(r, 7)), clean(cell(r, 8)), clean(cell(r, 9)), clean(cell(r, 10)),
                       clean(cell(r, 11)), clean(cell(r, 12)), link(cell(r, 13)), first_text(r[14:]), '']
    return base + ['', '', '', '', '', '', '', '', link(cell(r, 6)), clean(cell(r, 8)) or clean(cell(r, 7)), clean(cell(r, 9))]


def form_row(src, r):
    """BDM and MBA sheets: Timestamp, Name, Phone, Email, State, District, Years, Team managed, CTC, Expected CTC,
    Ready to travel, Notice, FMCG, Field sales, Resume link, [status...]"""
    return [src, ts_key(cell(r, 0)), clean(cell(r, 1)), phone10(cell(r, 2)), clean(cell(r, 3)), clean(cell(r, 4)), clean(cell(r, 5)),
            clean(cell(r, 6)), clean(cell(r, 7)), clean(cell(r, 8)), clean(cell(r, 9)), clean(cell(r, 10)), clean(cell(r, 11)),
            clean(cell(r, 12)), clean(cell(r, 13)), link(cell(r, 14)), first_text(r[15:]), '']


def main():
    out, counts, used = [], {}, []
    for src, work_name, cache_name, conv in (('BDE', 'bde_rows.json', 'bde_latest.json', bde_row),
                                              ('BDM', None, 'bdm_latest.json', lambda r: form_row('BDM', r)),
                                              ('MBA', 'mba_rows.json', 'mba_latest.json', lambda r: form_row('MBA', r))):
        rows, where = rows_from(work_name, cache_name)
        if where: used.append('%s <- %s' % (src, where))
        n = 0
        for r in rows:
            if not r or is_header(r): continue
            if not (clean(cell(r, 1)) or phone10(cell(r, 2))): continue    # nothing to show
            if phone10(cell(r, 2)).startswith('90000000') or clean(cell(r, 1)).upper().startswith('TEST'): continue   # form test entries
            out.append(conv(r)); n += 1
        counts[src] = n
    latest = max((r[1] for r in out if re.match(r'\d{4}-', r[1])), default='')
    data = {'cols': COLS, 'rows': out, 'latest': latest, 'counts': counts}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('public/applications.json', len(out), 'rows', counts, len(text), 'bytes;', '; '.join(used) or 'no sheet data found')


if __name__ == '__main__':
    main()
