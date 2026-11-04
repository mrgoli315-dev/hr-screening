#!/usr/bin/env python3
"""Naukri leads (v1.10): write public/naukri.json for the page's "Naukri leads" tab.
Run after sheets_export.py (step 7 of the sync; local/serve.py runs it too).

Source: pipeline/sheets/naukri_latest.json  ({"values": [[header...], [row...], ...]}) - the "Naukri leads"
Google Sheet that the Gmail Apps Script fills from Naukri's application e-mails (one row per application).
Columns are found by header name, so the sheet's column order does not matter. Until that sheet exists the
file is written with no rows and the tab shows "No Naukri leads yet".

Output: {"cols": [...], "rows": [[...], ...], "latest": "YYYY-MM-DD HH:MM:SS", "count": n}
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'pipeline', 'sheets', 'naukri_latest.json')
OUT = os.path.join(ROOT, 'public', 'naukri.json')

COLS = ['ts', 'n', 'ph', 'em', 'loc', 'ploc', 'desig', 'co', 'yrs', 'ctc', 'nt', 'edu', 'skills', 'job', 'res']
# header text (lower-cased, letters only) -> column key; several spellings per key
HEADERS = {
    'ts': ['timestamp', 'applied on', 'applied', 'date', 'received'],
    'n': ['name', 'candidate name', 'candidate'],
    'ph': ['phone', 'mobile', 'contact', 'phone number', 'mobile number'],
    'em': ['email', 'e-mail', 'email id'],
    'loc': ['current location', 'location', 'city'],
    'ploc': ['preferred location', 'preferred locations'],
    'desig': ['designation', 'current designation', 'current role', 'role'],
    'co': ['company', 'current company', 'employer'],
    'yrs': ['experience', 'total experience', 'years of experience', 'work experience'],
    'ctc': ['current ctc', 'ctc', 'salary', 'annual salary'],
    'nt': ['notice period', 'notice'],
    'edu': ['education', 'qualification', 'highest qualification', 'ug', 'pg'],
    'skills': ['key skills', 'skills'],
    'job': ['job title', 'job', 'applied for', 'position', 'job applied'],
    'res': ['resume link', 'resume', 'cv', 'resume url', 'file'],
}
LINK = re.compile(r'https?://\S+')


def norm(h):
    return re.sub(r'[^a-z]+', ' ', str(h or '').lower()).strip()


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def ts_key(s):
    """'10/16/2026 9:59:20' or '2026-10-16 09:59' -> 'YYYY-MM-DD HH:MM:SS'; anything else as typed."""
    s = clean(s)
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$', s)
    if m:
        mo, d, y, hh, mm, ss = m.groups()
        return '%s-%02d-%02d %02d:%s:%s' % (y, int(mo), int(d), int(hh or 0), mm or '00', ss or '00')
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?', s)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        return '%s-%s-%s %s:%s:%s' % (y, mo, d, hh or '00', mm or '00', ss or '00')
    return s


def phone10(s):
    d = re.sub(r'\D', '', s or '')
    if len(d) == 12 and d.startswith('91'): d = d[2:]
    if len(d) == 11 and d.startswith('0'): d = d[1:]
    return d


def main():
    rows_out = []
    if os.path.exists(SRC):
        d = json.load(open(SRC, encoding='utf-8'))
        values = d.get('values', []) if isinstance(d, dict) else d
        if values:
            header = [norm(h) for h in values[0]]
            idx = {}
            for key, names in HEADERS.items():
                for i, h in enumerate(header):
                    if h in names and key not in idx:
                        idx[key] = i
            missing = [k for k in ('n', 'ph') if k not in idx]
            if missing:
                raise SystemExit('naukri sheet: header row lacks a column for %s; header is %r' % (missing, values[0]))
            cell = lambda r, k: clean(r[idx[k]]) if k in idx and idx[k] < len(r) else ''
            for r in values[1:]:
                if not r or not (cell(r, 'n') or phone10(cell(r, 'ph'))): continue
                res = cell(r, 'res'); m = LINK.search(res); res = m.group(0) if m else res
                rows_out.append([ts_key(cell(r, 'ts')), cell(r, 'n'), phone10(cell(r, 'ph')), cell(r, 'em'), cell(r, 'loc'), cell(r, 'ploc'),
                                 cell(r, 'desig'), cell(r, 'co'), cell(r, 'yrs'), cell(r, 'ctc'), cell(r, 'nt'), cell(r, 'edu'),
                                 cell(r, 'skills'), cell(r, 'job'), res])
    latest = max((r[0] for r in rows_out if re.match(r'\d{4}-', r[0])), default='')
    data = {'cols': COLS, 'rows': rows_out, 'latest': latest, 'count': len(rows_out)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('public/naukri.json', len(rows_out), 'rows', len(text), 'bytes;', 'source: ' + ('pipeline/sheets/naukri_latest.json' if os.path.exists(SRC) else 'none yet (empty file)'))


if __name__ == '__main__':
    main()
