#!/usr/bin/env python3
"""Daily update helper for the MR.GOLISODA hiring shortlist page.
Run from anywhere:  python3 <bundle>/update.py <command>
  append --bde <tail.json> --bdm <tail.json> [--mba <tail.json>]   add newly fetched sheet rows (get_values result or a plain list of rows) to sheets/*.json
  new                                          find applicants not screened yet -> wait records + chunk/prompt files for the resume readers
  merge                                        fold new/out_run_*.json (reader results) into the page data
  build                                        rebuild data.js + the page, print a summary for the message
"""
import json, re, os, sys, glob, subprocess, collections, datetime, shutil
H = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(H, *a)

def p10(s):
    s = re.sub(r'\D', '', s or ''); return s[-10:] if len(s) >= 10 else s
def fid(link):
    m = re.search(r'/d/([A-Za-z0-9_-]{15,})', link or '') or re.search(r'id=([A-Za-z0-9_-]{15,})', link or '')
    return m.group(1) if m else ''
def url_of(link, f):
    if not f: return ''
    return ('https://docs.google.com/document/d/%s/edit' % f) if 'docs.google.com/document' in (link or '') else ('https://drive.google.com/file/d/%s/view' % f)
def title(n):
    n = re.sub(r'\s+', ' ', (n or '').strip())
    if n.isupper() or n.islower(): n = ' '.join(w.capitalize() if len(w) > 1 else w.upper() for w in n.split(' '))
    return n
def yn(v): return (v or '').strip().lower()
def formline(yrs, fmcg, fs, tv, tm=''):
    bits = []
    if yrs: bits.append(re.sub(r'\s*years?', '', yrs) + ' yrs')
    bits.append('FMCG ' + ('yes' if yn(fmcg) == 'yes' else 'no'))
    bits.append('field sales ' + ('yes' if yn(fs) == 'yes' else 'no'))
    if yn(tv) == 'no': bits.append('not ready to travel')
    if tm and tm.lower() != 'none': bits.append('managed ' + tm)
    return 'Resume not read yet. Form: ' + ', '.join(bits) + '.'

def load_values(path):
    """Accepts a saved get_values result ({range, values}), a bare list of rows, or a get_spreadsheet grid result."""
    d = json.load(open(path))
    if isinstance(d, list): return d
    if 'values' in d: return d['values']
    rows = []
    for sh in d.get('sheets', []):
        for data in sh.get('data', []):
            for r in data.get('rowData', []):
                rows.append([c.get('formattedValue', '') for c in r.get('values', [])])
    return rows

def cmd_append(args):
    """append --bde <file> --bdm <file>: add the newly fetched tail rows to sheets/bde_latest.json and bdm_latest.json"""
    bde = bdm = mba = None
    for i, a in enumerate(args):
        if a == '--bde': bde = args[i + 1]
        if a == '--bdm': bdm = args[i + 1]
        if a == '--mba': mba = args[i + 1]
    os.makedirs(P('sheets'), exist_ok=True)
    def merge(path, rows, header=None):
        cur = json.load(open(path))['values'] if os.path.exists(path) else []
        seen = {(r[0], p10(r[2])) for r in cur if len(r) > 2}
        added = 0
        for r in rows:
            if len(r) < 3 or not r[2] or (header and r[0] == header): continue
            if (r[0], p10(r[2])) in seen: continue
            cur.append(r); seen.add((r[0], p10(r[2]))); added += 1
        json.dump({'values': cur}, open(path, 'w'), ensure_ascii=False)
        return added, len(cur)
    if bde:
        a, t = merge(P('sheets', 'bde_latest.json'), load_values(bde))
        print('bde: added', a, 'rows, total', t)
    if bdm:
        rows = load_values(bdm)
        a, t = merge(P('sheets', 'bdm_latest.json'), rows, header='Timestamp')
        allrows = json.load(open(P('sheets', 'bdm_latest.json')))['values']
        json.dump([[r[0], r[1], r[2]] for r in allrows if r[0] and r[0] != 'Timestamp'], open(P('sheets', 'bdm_ts_latest.json'), 'w'), ensure_ascii=False)
        print('bdm: added', a, 'rows, total', t)
    if mba:
        a, t = merge(P('sheets', 'mba_latest.json'), load_values(mba), header='Timestamp')
        print('mba: added', a, 'rows, total', t)
    for name in ('bde_latest.json', 'bdm_latest.json', 'mba_latest.json'):
        pth = P('sheets', name)
        if os.path.exists(pth):
            n = len(json.load(open(pth))['values']); print(name, 'rows =', n, '-> next fetch starts at sheet row', n + 1)

def load_known():
    raw = open(P('v3', 'screened_phones.txt')).read()
    sp = set(re.findall(r'\d{10}', raw))
    nr = json.load(open(P('new', 'new_rated.json')))
    return sp, nr

def cmd_new(args):
    sp, nr = load_known()
    known = sp | {r['ph'] for r in nr}
    bde = {}
    for r in json.load(open(P('sheets', 'bde_latest.json')))['values']:
        ph = p10(r[2] if len(r) > 2 else '')
        if not ph or ph in known: continue
        bde[ph] = r + [''] * (14 - len(r))
    bdm = {}
    bdm_path = P('sheets', 'bdm_latest.json')
    if os.path.exists(bdm_path):
        for r in json.load(open(bdm_path))['values']:
            if not r or r[0] == 'Timestamp': continue
            ph = p10(r[2] if len(r) > 2 else '')
            if not ph or ph in known: continue
            bdm[ph] = r + [''] * (17 - len(r))
    mba = {}
    mba_path = P('sheets', 'mba_latest.json')
    if os.path.exists(mba_path):
        for r in json.load(open(mba_path))['values']:
            if not r or r[0] == 'Timestamp': continue
            ph = p10(r[2] if len(r) > 2 else '')
            if not ph or ph in known or ph in bdm or ph in bde: continue
            if ph.startswith('90000000') or (r[1] or '').strip().upper().startswith('TEST'): continue   # form test entries
            mba[ph] = r + [''] * (15 - len(r))
    # form fields for build.py
    with open(P('forms', 'bde_new.txt'), 'a') as f:
        for ph, r in bde.items():
            f.write('|'.join([r[0], r[1], ph, r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], fid(r[13])]) + '\n')
    with open(P('forms', 'bdm_fields.txt'), 'a') as f:
        for ph, r in list(bdm.items()) + list(mba.items()):
            f.write('|'.join([ph, r[6], r[8], r[9], r[11], r[10], r[12], r[13], r[7]]) + '\n')
    items, added = [], []
    for ph, r in bde.items():
        rec = {'ph': ph, 'src': 'BDE', 'n': title(r[1]), 'c': '', 'fd': r[5], 'st': r[4], 'age': None, 'ae': '', 'yrs': None, 'lang': '', 'ro': ['BDE'], 'lv': 'wait',
               'exp': formline(r[6], r[11], r[12], r[9]), 'ctc': '', 'ask': '', 'why': '', 'fid': fid(r[13])}
        nr.append(rec); added.append(rec)
        items.append({'src': 'BDE', 'n': rec['n'], 'ph': ph, 'st': r[4], 'fd': r[5], 'url': url_of(r[13], rec['fid']), 'fid': rec['fid'],
                      'form': 'yrs %s; CTC %s -> %s; travel %s; notice %s; FMCG %s; field sales %s' % (r[6], r[7], r[8], r[9], r[10], r[11], r[12])})
    for ph, r in bdm.items():
        rec = {'ph': ph, 'src': 'BDM', 'n': title(r[1]), 'c': '', 'fd': r[5], 'st': r[4], 'age': None, 'ae': '', 'yrs': None, 'lang': '', 'ro': ['BDM'], 'lv': 'wait',
               'exp': formline(r[6], r[12], r[13], r[10], r[7]), 'ctc': '', 'ask': '', 'why': '', 'fid': fid(r[14])}
        nr.append(rec); added.append(rec)
        items.append({'src': 'BDM', 'n': rec['n'], 'ph': ph, 'st': r[4], 'fd': r[5], 'url': url_of(r[14], rec['fid']), 'fid': rec['fid'],
                      'form': 'yrs %s; team managed %s; CTC %s -> %s; travel %s; notice %s; FMCG %s; field sales %s' % (r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13])})
    for ph, r in mba.items():
        rec = {'ph': ph, 'src': 'MBA', 'n': title(r[1]), 'c': '', 'fd': r[5], 'st': r[4], 'age': None, 'ae': '', 'yrs': None, 'lang': '', 'ro': ['BDE', 'BDM'], 'lv': 'wait',
               'exp': formline(r[6], r[12], r[13], r[10], r[7]), 'ctc': '', 'ask': '', 'why': '', 'fid': fid(r[14]), 'edu': ''}
        nr.append(rec); added.append(rec)
        items.append({'src': 'MBA', 'n': rec['n'], 'ph': ph, 'st': r[4], 'fd': r[5], 'url': url_of(r[14], rec['fid']), 'fid': rec['fid'],
                      'form': 'MBA-preferred form (BDE up to 40k/month, BDM up to 70k/month); yrs %s; team managed %s; CTC %s -> %s; travel %s; notice %s; FMCG %s; field sales %s' % (r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13])})
    # earlier 'wait' records whose resume was never read: try again
    have = {it['ph'] for it in items}
    for rec in nr:
        if rec['lv'] == 'wait' and rec['ph'] not in have and rec.get('fid'):
            items.append({'src': rec['src'], 'n': rec['n'], 'ph': rec['ph'], 'st': rec['st'], 'fd': rec['fd'], 'fid': rec['fid'],
                          'url': 'https://drive.google.com/file/d/%s/view' % rec['fid'], 'form': rec.get('exp', '')})
    json.dump(nr, open(P('new', 'new_rated.json'), 'w'), ensure_ascii=False, indent=0)
    items = [it for it in items if it['url']]
    for old in glob.glob(P('new', 'chunk_run_*.json')) + glob.glob(P('new', 'prompt_run_*.txt')): os.remove(old)
    tpl = open(P('new', 'prompt_template.txt')).read()
    size = 10; n = 0
    for i in range(0, len(items), size):
        n += 1; part = items[i:i + size]; nn = '%02d' % n
        json.dump(part, open(P('new', 'chunk_run_%s.json' % nn), 'w'), ensure_ascii=False, indent=1)
        open(P('new', 'prompt_run_%s.txt' % nn), 'w').write(tpl.replace('{LIST}', P('new', 'chunk_run_%s.json' % nn)).replace('{OUT}', P('new', 'out_run_%s.json' % nn)).replace('{COUNT}', str(len(part))).replace('{NN}', nn))
    print(json.dumps({'new_bde': len(bde), 'new_bdm': len(bdm), 'new_mba': len(mba), 'to_read': len(items), 'chunks': n,
                      'names': [it['n'] + ' (' + it['fd'] + ')' for it in items]}, ensure_ascii=False, indent=1))

KEEP = ['ph', 'src', 'n', 'c', 'fd', 'st', 'age', 'ae', 'yrs', 'lang', 'ro', 'lv', 'exp', 'ctc', 'ask', 'why', 'fid', 'edu']
def cmd_merge(args):
    sp, nr = load_known()
    C = json.load(open(P('co', 'companies.json')))
    outs = []
    files = sorted(glob.glob(P('new', 'out_run_*.json')))
    for fn in files:
        try: outs += json.load(open(fn))
        except Exception as e: print('bad file', fn, e)
    by = {r['ph']: r for r in outs if r.get('ph')}
    n = 0
    for i, r in enumerate(nr):
        o = by.get(r['ph'])
        if not o: continue
        new = {k: o.get(k, r.get(k, '')) for k in KEEP}
        new['src'] = r['src']; new['fid'] = r.get('fid') or o.get('fid', '')
        if not new['fd']: new['fd'] = r['fd']
        if not new['st']: new['st'] = r['st']
        if isinstance(new.get('age'), str): new['age'] = None
        if new['lv'] not in ('strong', 'medium', 'check', 'hide'): new['lv'] = 'check'
        nr[i] = new; n += 1
        if o.get('co'): C['S:' + r['ph']] = {'co': o['co'][:5], 'now': o.get('now', '')}
    json.dump(nr, open(P('new', 'new_rated.json'), 'w'), ensure_ascii=False, indent=0)
    json.dump(C, open(P('co', 'companies.json'), 'w'), ensure_ascii=False)
    sp |= {r['ph'] for r in nr}
    open(P('v3', 'screened_phones.txt'), 'w').write(','.join(sorted(sp)))
    os.makedirs(P('new', 'done'), exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    for fn in files: shutil.move(fn, P('new', 'done', stamp + '_' + os.path.basename(fn)))
    print(json.dumps({'merged': n, 'levels': dict(collections.Counter(r['lv'] for r in outs)), 'still_waiting': sum(1 for r in nr if r['lv'] == 'wait')}))

def cmd_build(args):
    out = subprocess.run([sys.executable, P('v3', 'build.py')], capture_output=True, text=True, cwd=P('v3'))
    if out.returncode: print(out.stdout[-2000:], out.stderr[-3000:]); sys.exit(1)
    out2 = subprocess.run([sys.executable, P('v3', 'assemble.py')], capture_output=True, text=True, cwd=P('v3'))
    if out2.returncode: print(out2.stdout[-2000:], out2.stderr[-3000:]); sys.exit(1)
    shutil.copy(P('v3', 'sales-hiring-shortlist.html'), P('v3', 'combined-hiring-shortlist.html'))
    s = open(P('v3', 'data.js')).read()
    D = json.loads(re.search(r'const D=(.*?);\nconst P=', s, re.S).group(1))
    PP = {p['id']: p for p in json.loads(re.search(r'const P=(.*?);\nconst HIDDEN=', s, re.S).group(1))}
    HID = json.loads(re.search(r'const HIDDEN=(.*?);\nconst HIDDEN_APP=', s, re.S).group(1))
    today = datetime.date.today().isoformat()
    tp = [d for d in D if today in (d.get('ad'), d.get('al'))]
    th = [h for h in HID if len(h) > 4 and today in (h[3], h[4])]
    lv = collections.Counter(d['lv'] for d in tp)
    strong = [d['n'] + ' (' + (d.get('fd') or d.get('c') or '') + ') -> ' + ', '.join(PP[i]['title'].split(' · ')[-1] for i in d.get('pos', [])[:2]) for d in tp if d['lv'] == 'strong']
    print(json.dumps({'page_candidates': len(D), 'today_applications': len(tp) + len(th), 'today_rated': dict(lv), 'today_not_usable': len(th),
                      'today_waiting': sum(1 for d in tp if d['lv'] == 'wait'), 'today_strong': strong, 'transfers': sum(1 for d in D if d.get('tf')),
                      'html': P('v3', 'combined-hiring-shortlist.html'), 'bytes': os.path.getsize(P('v3', 'combined-hiring-shortlist.html'))}, ensure_ascii=False, indent=1))

def cmd_rows(args):
    for name, tab in (('bde_latest.json', "'Applications'!A%d:P1000"), ('bdm_latest.json', "'All Applications'!A%d:Q1000"), ('mba_latest.json', "'All Applications'!A%d:O1000 (MBA sheet 1sGCaXYi0aCuOtFLfq40QAwKBEKg-hytw9-LAdNFXKwQ)")):
        pth = P('sheets', name)
        n = len(json.load(open(pth))['values']) if os.path.exists(pth) else 0
        print(name, 'has', n, 'rows -> fetch range', tab % (n + 1))

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'rows': cmd_rows, 'append': cmd_append, 'new': cmd_new, 'merge': cmd_merge, 'build': cmd_build}.get(cmd, lambda a: print(__doc__))(sys.argv[2:])
