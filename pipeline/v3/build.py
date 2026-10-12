#!/usr/bin/env python3
"""Merge sheet + HR-app candidates, apply the location/language rules, match to open positions.
Output: v3/data.js  (consumed by v3/page.tpl.html)"""
import json, re, os, collections

H = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(H, '..', 'app')

sheet = json.load(open(os.path.join(H, 'sheet.json')))
meta = json.load(open(os.path.join(APP, 'app_meta.json')))
rated = {r['k']: r for r in json.load(open(os.path.join(APP, 'app_rated.json')))}
ocr_path = os.path.join(APP, 'app_rated_ocr.json')
if os.path.exists(ocr_path):
    for r in json.load(open(ocr_path)):
        rated[r['k']] = r
POS = json.load(open(os.path.join(APP, 'positions.json')))
POSMETA = json.load(open(os.path.join(APP, 'posmeta.json')))
POSID = {p[0]: p for p in POS}

# ---------------------------------------------------------------- helpers
def n10(s):
    d = re.sub(r'\D', '', s or '')
    return d[-10:] if len(d) >= 10 else ''

def wa_number(s):
    d = re.sub(r'\D', '', s or '')
    if len(d) == 10: return '91' + d
    if len(d) == 12 and d.startswith('91'): return d
    if len(d) == 11 and d.startswith('0'): return '91' + d[1:]
    if len(d) > 10: return d
    return ''

def show_phone(s):
    d = re.sub(r'\D', '', s or '')
    if len(d) == 12 and d.startswith('91'): d = d[2:]
    if len(d) == 11 and d.startswith('0'): d = d[1:]
    return d if d else (s or '')

def clean(s):
    return re.sub(r'[^a-z]+', ' ', (s or '').lower()).strip()

STATE_FIX = {'jharkand': 'Jharkhand', 'pondicherry': 'Puducherry', 'orissa': 'Odisha', 'new delhi': 'Delhi',
             'nct of delhi': 'Delhi', 'tamilnadu': 'Tamil Nadu', 'karnatka': 'Karnataka'}
def fix_state(s):
    s = (s or '').strip()
    return STATE_FIX.get(s.lower(), s)

GEO = json.load(open(os.path.join(APP, 'geo.json')))   # city aliases + position areas (data file, edited without touching this script)
ALIAS = {}
for _canon, _names in GEO['alias'].items():
    for n in [_canon] + list(_names):
        ALIAS[clean(n)] = _canon

def canon(s):
    c = clean(s)
    if not c: return ''
    if c in ALIAS: return ALIAS[c]
    for tok in sorted(ALIAS, key=len, reverse=True):     # e.g. "bengaluru urban district"
        if len(tok) > 4 and re.search(r'\b' + re.escape(tok) + r'\b', c):
            return ALIAS[tok]
    return c

AREA = {city: (set(v[0]), set(v[1])) for city, v in GEO['area'].items()}   # position city -> (local districts, nearby districts)
CHENNAI_AREA = AREA['Chennai'][0]
FE_LANG = {'Andhra Pradesh': 'telugu', 'Telangana': 'telugu', 'Karnataka': 'kannada', 'Tamil Nadu': 'tamil',
           'Kerala': 'malayalam', 'Gujarat': 'gujarati', 'Maharashtra': 'marathi', 'Delhi': 'hindi'}
LANG_HOME = {'telugu': {'Andhra Pradesh', 'Telangana'}, 'kannada': {'Karnataka'}, 'tamil': {'Tamil Nadu', 'Puducherry'},
             'malayalam': {'Kerala'}, 'gujarati': {'Gujarat'}, 'marathi': {'Maharashtra'}, 'hindi': {'Delhi', 'Uttar Pradesh', 'Madhya Pradesh', 'Rajasthan', 'Haryana', 'Bihar', 'Jharkhand', 'Chhattisgarh'}}
STATE_WIDE = {'FM', 'SH', 'LAUNCH'}
ROLE_OK = {'BDE': {'BDE'}, 'LAUNCH': {'LAUNCH'}, 'BDM': {'BDM', 'ASM'}, 'SH': {'SH'}, 'FM': {'FM'}, 'FE': {'FE'},
           'OPX': {'OPX', 'OPS'}, 'PUR': {'PUR'}, 'DISP': {'DISP'}, 'DMK': {'DMK'}, 'ITX': {'ITX'}, 'LND': {'LND'}}
STAGE_FIX = {'Salary discussio': 'Salary discussion'}

def status_text(stage, status, exit_):
    stage = STAGE_FIX.get(stage, stage)
    if status == 'active': t = 'In process · ' + stage
    elif status == 'offer_released': t = 'Offer sent'
    elif status == 'joined': t = 'Joined'
    elif status == 'attrition': t = 'Worked here, left'
    elif status == 'dropped': t = 'Dropped at ' + stage
    elif status == 'rejected': t = 'Rejected at ' + stage
    else: t = (status or '') + ' · ' + stage
    if exit_: t += ' — ' + exit_.strip()[:60]
    return t

NEG = re.compile(r'not interest|another offer|other offer|got placed|placed|joined (in|at|other|another)|not willing|not looking|already working', re.I)


# ---------------------------------------------------------------- application dates (first and latest form submission per phone)
import csv as _csv
_rows = list(_csv.reader(open(os.path.join(H, '..', 'uploads', 'bde_export_oct3.csv'), encoding='utf-8', errors='replace')))
TS, TSL, TAT = {}, {}, {}
def _ts(s):
    m = re.match(r'\s*(\d{1,2})/(\d{1,2})/(\d{4})', s or '')
    return '%s-%02d-%02d' % (m.group(3), int(m.group(1)), int(m.group(2))) if m else ''
def _tm(s):
    m = re.search(r'\s(\d{1,2}):(\d{2})', s or '')
    return '%02d:%s' % (int(m.group(1)), m.group(2)) if m else ''
def _tsput(ph, ts):
    ph, dd = n10(ph), _ts(ts)
    if not (ph and dd): return
    if ph not in TS or dd < TS[ph]: TS[ph] = dd
    if ph not in TSL or (dd + _tm(ts)) >= (TSL[ph] + TAT.get(ph, '')): TSL[ph] = dd; TAT[ph] = _tm(ts)
SHEETS = os.path.join(H, '..', 'sheets')
for r in json.load(open(os.path.join(SHEETS, 'bde_latest.json')))['values']:
    if len(r) > 2: _tsput(r[2], r[0])
for ts, _n, ph in json.load(open(os.path.join(SHEETS, 'bdm_ts_latest.json'))): _tsput(ph, ts)
MBA_FORM = set()   # phones that applied through the MBA-preferred form
if os.path.exists(os.path.join(SHEETS, 'mba_latest.json')):
    for r in json.load(open(os.path.join(SHEETS, 'mba_latest.json')))['values']:
        if len(r) > 2 and r[0] != 'Timestamp' and not str(r[2]).startswith('90000000'):
            _tsput(r[2], r[0]); MBA_FORM.add(n10(r[2]))
for r in _rows[1:]:
    if len(r) > 2: _tsput(r[2], r[0])
# HR app: earliest date on the candidate's position entries
APPDATE = {}
for k, raw, email, name, entries, nk, exptag, tstat in meta:
    ds = [e[4] for e in entries if len(e) > 4 and e[4]]
    if ds: APPDATE[k] = min(ds)
    if n10(raw) and ds: APPDATE.setdefault('ph:' + n10(raw), min(ds))

# ---------------------------------------------------------------- build candidate list
C = []          # unified candidates
by_phone = {}

for d in sheet['D']:
    rec = dict(d)
    rec['src'] = 'S'
    rec['ap'] = []
    rec['st'] = fix_state(rec.get('st'))
    rec['dc'] = canon(rec.get('fd')) or canon(rec.get('c'))
    rec['wa'] = wa_number(rec.get('ph'))
    rec['ph'] = show_phone(rec.get('ph'))
    if not rec.get('lang'):
        rec['lang'] = ''
    C.append(rec)
    if n10(d.get('ph')): by_phone[n10(d['ph'])] = rec

# ---- new sheet applicants (BDE + BDM forms) screened from Drive
new_hidden = []
new_path = os.path.join(H, '..', 'new', 'new_rated.json')
if os.path.exists(new_path):
    for r in json.load(open(new_path)):
        rec = {'n': r['n'], 'c': r.get('c', ''), 'st': fix_state(r.get('st', '')), 'fd': r.get('fd', ''),
               'ph': show_phone(r['ph']), 'wa': wa_number(r['ph']),
               'age': (str(r['age']) if r.get('age') else (r.get('ae') or '')), 'ae': 0 if r.get('age') else (1 if r.get('ae') else 0),
               'yrs': r.get('yrs'), 'ro': r.get('ro', []), 'lv': r['lv'], 'exp': r.get('exp', ''), 'ask': r.get('ask', ''),
               'ctc': r.get('ctc', ''), 'mo': None, 'res': r.get('fid', ''), 'lang': r.get('lang', ''),
               'src': 'S', 'ap': [], 'nw': 1, 'form': r.get('src', '')}
        if r.get('edu'): rec['edu'] = r['edu']
        if n10(r['ph']) in MBA_FORM and rec['form'] != 'MBA': rec['form2'] = 'MBA'
        rec['dc'] = canon(rec['fd']) or canon(rec['c'])
        cc = canon(rec['c'])
        if cc and rec['dc'] and cc != rec['dc']: rec['mv'] = 1
        if rec['lv'] == 'hide':
            new_hidden.append([rec['n'], 'Not rated', r.get('why') or 'Nothing usable', TS.get(n10(r['ph']), ''), TSL.get(n10(r['ph']), ''), TAT.get(n10(r['ph']), ''), wa_number(r['ph'])])
            continue
        C.append(rec)
        if n10(r['ph']): by_phone[n10(r['ph'])] = rec

no_resume = []     # app people we could not screen
app_hidden = []
dup_merged = 0
for k, raw, email, name, entries, nk, exptag, tstat in meta:
    ap = [[e[0], status_text(e[1], e[2], e[3]), e[2], (e[3] or '')] for e in entries]
    joined = any(e[2] == 'joined' for e in entries)
    r = rated.get(k)
    ph10 = n10(raw)
    if ph10 and ph10 in by_phone:            # same person is in the sheet
        s = by_phone[ph10]
        s['ap'] += ap
        s['src'] = 'SA'
        if joined: s['joined'] = True
        dup_merged += 1
        continue
    if r is None:
        no_resume.append({'n': name.strip(), 'ph': show_phone(raw), 'ap': ap, 'why': tstat or 'no file', 'nk': exptag, 'joined': joined})
        continue
    rec = {
        'n': r['n'], 'c': r.get('c', ''), 'st': fix_state(r.get('st', '')), 'fd': r.get('fd', ''),
        'loc': r.get('loc', ''), 'ph': show_phone(raw), 'wa': wa_number(raw),
        'age': (str(r['age']) if r.get('age') else (r.get('ae') or '')), 'ae': 0 if r.get('age') else (1 if r.get('ae') else 0),
        'yrs': r.get('yrs'), 'lang': r.get('lang', ''), 'ro': r.get('ro', []), 'lv': r.get('lv'),
        'exp': r.get('exp', ''), 'ask': r.get('ask', ''), 'ctc': r.get('ctc', ''), 'mo': None,
        'res': '', 'src': 'A', 'ap': ap, 'k': k, 'nk': exptag, 'why': r.get('why', ''),
    }
    if not rec['ph'] and email: rec['em'] = email
    rec['dc'] = canon(rec['fd']) or canon(rec['c'])
    if joined: rec['joined'] = True
    if rec['lv'] == 'hide':
        app_hidden.append(rec)
        continue
    C.append(rec)

# ---------------------------------------------------------------- language helper
def lang_status(rec, need):
    toks = [t.strip().lower() for t in re.split(r'[,;]', rec.get('lang') or '') if t.strip()]
    for t in toks:
        if need in t:
            return 'likely' if 'likely' in t else 'yes'
    if rec.get('st') in LANG_HOME.get(need, set()):
        return 'likely'
    return ''

# ---------------------------------------------------------------- matching
LVS = {'strong': 30, 'medium': 20, 'check': 10, 'wait': 2}   # wait = applied, resume not read yet
matches = {}
farlist = {}
# how many people the HR app already holds for each position
app_cnt = collections.defaultdict(lambda: [0, 0])
for k, raw, email, name, entries, nk, exptag, tstat in meta:
    for e in entries:
        app_cnt[e[0]][0] += 1
        if e[2] in ('active', 'offer_released'): app_cnt[e[0]][1] += 1
for p in POS:
    pid, state, role, title, city, seats, status, note = p
    ok_roles = ROLE_OK[role]
    loc_l, loc_n = AREA.get(city, (set(), set()))
    out = []
    for i, c in enumerate(C):
        if c.get('taken') or c.get('joined'): continue
        if c.get('lv') not in LVS: continue
        ro = c.get('ro') or []
        hit = [r for r in ro if r in ok_roles]
        if not hit: continue
        applied = [a for a in c.get('ap', []) if a[0] == pid]
        tier, flag = '', ''
        if role == 'FE':
            need = FE_LANG.get(state, '')
            ls = lang_status(c, need) if need else 'yes'
            if not ls: continue
            tier = 'chennai' if (c.get('st') == 'Tamil Nadu' and c.get('dc') in CHENNAI_AREA) else 'move'
            flag = ls
        else:
            same_state = c.get('st') == state
            dc = c.get('dc')
            if dc and dc in loc_l: tier = 'local'
            elif dc and dc in loc_n: tier = 'nearby'
            elif role in STATE_WIDE and same_state: tier = 'state'
            elif state == 'Delhi' and dc in loc_l: tier = 'local'
            elif not c.get('st') and applied: tier = 'unknown'     # no location on resume, but applied here
            else: continue
            if tier in ('local', 'nearby') and not same_state and state != 'Delhi':
                continue
        score = LVS[c['lv']] + (5 if ro and ro[0] in ok_roles else 0)
        score += {'local': 4, 'chennai': 4, 'nearby': 1, 'state': 0, 'move': 0, 'unknown': -2}[tier]
        if role == 'FE' and flag == 'yes': score += 2
        if applied: score += 2
        neg = ''
        for a in c.get('ap', []):
            if a[3] and NEG.search(a[3]):
                neg = a[3]
        if neg: score -= 8
        out.append([i, tier, flag, 1 if applied else 0, score, neg[:50]])
    out.sort(key=lambda x: -x[4])
    matches[pid] = out
    # applicants of THIS position who were left out because of location / language
    got = {m[0] for m in out}
    far = []
    for i, c in enumerate(C):
        if i in got or c.get('joined') or c.get('lv') not in LVS: continue
        if not any(a[0] == pid for a in c.get('ap', [])): continue
        if not any(r in ok_roles for r in (c.get('ro') or [])): continue
        if role == 'FE':
            why = 'no ' + FE_LANG.get(state, '').title() + ' on resume'
        else:
            where = c.get('fd') or c.get('c') or c.get('st') or 'unknown'
            why = 'lives in ' + where + ((', ' + c['st']) if c.get('st') and c.get('st') != state else '')
        far.append([i, why])
    farlist[pid] = far

# ---------------------------------------------------------------- per-candidate list of matched positions
cand_pos = collections.defaultdict(list)
cand_score = collections.defaultdict(dict)
for pid, lst in matches.items():
    for m in lst:
        cand_pos[m[0]].append(pid); cand_score[m[0]][pid] = m[4]
# best-scored position first; the first one is the candidate's primary position (used to count each lead once)
_filled = {p[0] for p in POS if 'mark Filled' in (p[7] or '')}
for i in cand_pos:
    cand_pos[i].sort(key=lambda pid: (pid in _filled, -cand_score[i][pid]))

# ---------------------------------------------------------------- outputs
def jsdump(name, obj):
    return 'const ' + name + '=' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n'

DEPT_FIX = {'BDE': 'Post Sales', 'Sales': 'Post Sales'}  # odd department names in the app, folded so the filter groups them

POSOUT = []
for p in POS:
    pid, state, role, title, city, seats, status, note = p
    POSOUT.append({'id': pid, 'st': state, 'role': role, 'title': title, 'city': city, 'seats': seats,
                   'status': status, 'note': note, 'm': [[m[0], m[1], m[2], m[3], m[5]] for m in matches[pid]],
                   'x': farlist.get(pid, []), 'inapp': app_cnt[pid][0], 'active': app_cnt[pid][1],
                   'dept': DEPT_FIX.get(POSMETA[pid][0], POSMETA[pid][0]), 'desig': POSMETA[pid][1], 'owner': POSMETA[pid][2],
                   'prio': POSMETA[pid][3], 'opened': POSMETA[pid][4],
                   'health': ('Stuck' if 'stuck' in status.lower() else 'Slipping' if 'slipping' in status.lower()
                              else 'Temporarily closed' if 'temporarily' in status.lower() else 'On target')})

for i, c in enumerate(C):
    c['pos'] = cand_pos.get(i, [])
    c['pp'] = c['pos'][0] if c['pos'] else ''

CLOSED = {
 '1w9h8kbr': 'Maharashtra · BDE Executive · Chandrapur', 'rkewwibv': 'Maharashtra · BDE · Chandrapur',
 'e6vixigk': 'Maharashtra · BDE · Ahmednagar', '99h0elbc': 'Tamil Nadu · BDE · Coimbatore',
 'xsdtmgb1': 'Maharashtra · BDE Executive · Ahmednagar', '9e3tel9i': 'Andhra Pradesh · BDE · Nandyal',
 'w8ssfce8': 'Maharashtra · State Head · Mumbai', 'eh5t9oc8': 'Maharashtra · Post Sales Executive · Nashik',
 'dksj2g5s': 'Telangana · BDE · Hyderabad', 'cpzmvte6': 'Maharashtra · BDE · Akola',
 'llc2g4lo': 'Tamil Nadu · BDE · Erode', '6n65duv5': 'Andhra Pradesh · BDE · Rayachoti',
 'g75rexe9': 'Tamil Nadu · MIS Executive · Chennai', 'n9uu8huf': 'Tamil Nadu · Digital Marketing Executive · Chennai',
 'tli8ivkt': 'Andhra Pradesh · BDE · Nellore', 'puihlq82': 'Andhra Pradesh · BDE · Vijayawada',
 'q7c9jhyf': 'Jharkhand · BDM · Jamshedpur', 'qkj565tf': 'Karnataka · State Head · Bengaluru',
 '020s5rwy': 'Tamil Nadu · HR Executive · Chennai', 'ix7p1cnu': 'Maharashtra · Franchise Manager',
}
PLAB = {p[0]: p[1] + ' · ' + p[3] for p in POS}
for k, v in CLOSED.items(): PLAB[k] = v + ' (filled)'
missing_lab = {e[0] for x in meta for e in x[4]} - set(PLAB)
assert not missing_lab, missing_lab

NOTES = json.load(open(os.path.join(APP, 'notes.json')))   # page notes: positions missing in the HR app, data issues
MISSING = NOTES['missing']
ISSUES = NOTES['issues']


# ---------------------------------------------------------------- row details: companies, salary, joining, experience
FORMS = os.path.join(H, '..', 'forms')
COMP = json.load(open(os.path.join(H, '..', 'co', 'companies.json')))

def _lpa(raw):
    """Turn a typed salary (3.3 / 330000 / 25000 / 4.5LPA / 40k / 3.60 lac) into lakhs per year."""
    s = str(raw or '').lower().replace('₹', '').replace('rs.', '').replace('rs', '').replace('inr', '')
    s = s.replace('/-', '').replace(',', '').replace(' ', '').strip()
    if not s: return None
    m = re.search(r'\d+(?:\.\d+)?', s)
    if not m: return None
    num = float(m.group()); rest = s[m.end():]
    if num == 0: return 0.0
    if rest.startswith('l'): return num                       # 4.5lpa, 3.6lac, 6l
    if rest.startswith('k'): return num * 12 / 100            # 40k a month
    if num >= 100000: return num / 100000                     # yearly rupees
    if num >= 1000: return num * 12 / 100000                  # monthly rupees
    if num < 100: return num                                  # already in lakhs
    return None

def _fmt(x):
    if x is None: return '?'
    if x == 0: return '0'
    return ('%.2f' % x).rstrip('0').rstrip('.') + 'L'

def _sal(c, e):
    a, b = _lpa(c), (None if str(e or '').strip().lower() in ('', 'na') else (_lpa(c) if str(e).strip().lower() == 'same' else _lpa(e)))
    if a in (None, 0) and b in (None, 0): return ''
    return (_fmt(a) if a not in (None, 0) else '?') + ' → ' + (_fmt(b) if b not in (None, 0) else '?')

def _notice(s):
    s = (s or '').strip()
    if not s: return ''
    if re.search(r'immediate', s, re.I): return 'Immediate'
    return s

def _yb(s):
    s = (s or '').strip()
    return re.sub(r'\s*years?', ' yrs', s).replace('yrs yrs', 'yrs') if s else ''

FORM = {}
def _put(ph, **kw):
    ph = n10(ph)
    if ph: FORM.setdefault(ph, {}).update({k: v for k, v in kw.items() if v not in (None, '')})

# 1) BDE form export of Oct 3 (older rows; the live sheet no longer has these columns for them)
for r in _rows[1:]:
    if len(r) < 13: continue
    _put(r[2], yb=_yb(r[6]), sal=_sal(r[7], r[8]), nt=_notice(r[10]), tv=r[9], fmcg=r[11], fs=r[12])
# 2) BDE form, live rows from Oct 5 onwards
for l in open(os.path.join(FORMS, 'bde_new.txt')).read().strip().split('\n'):
    r = l.split('|')
    _put(r[2], yb=_yb(r[5]), sal=_sal(r[6], r[7]), nt=_notice(r[9]), tv=r[8], fmcg=r[10], fs=r[11])
# 3) BDM form, live
for l in open(os.path.join(FORMS, 'bdm_fields.txt')).read().strip().split('\n'):
    r = l.split('|')
    _put(r[0], yb=_yb(r[1]), sal=_sal(r[2], r[3]), nt=_notice(r[4]), tv=r[5], fmcg=r[6], fs=r[7], tm=r[8])

def _key(d): return ('A:' + d['k']) if d.get('src') == 'A' else ('S:' + n10(d['ph']))

_stat = collections.Counter()
for d in C:
    fd_ = TS.get(n10(d.get('ph'))) if d.get('src') != 'A' else None
    ad_ = APPDATE.get(d.get('k')) if d.get('src') == 'A' else APPDATE.get('ph:' + n10(d.get('ph')))
    if fd_: d['ad'], d['adk'] = fd_, 'form'
    elif ad_: d['ad'], d['adk'] = ad_, 'app'
    else: d['ad'], d['adk'] = '', ''
    la_ = TSL.get(n10(d.get('ph'))) if d.get('src') != 'A' else None
    if la_ and la_ != d['ad']: d['al'] = la_
    if d['adk'] == 'form' and TAT.get(n10(d.get('ph'))): d['at'] = TAT[n10(d.get('ph'))]
    _stat['ad_form'] += (d['adk'] == 'form'); _stat['ad_app'] += (d['adk'] == 'app'); _stat['ad_none'] += (not d['ad'])
    co = COMP.get(_key(d)) or {}
    d['co'] = co.get('co') or []
    now = co.get('now') or ''
    f = FORM.get(n10(d.get('ph'))) if d.get('src') != 'A' else None
    if d.get('src') == 'A' and FORM.get(n10(d.get('ph'))): f = FORM.get(n10(d.get('ph')))
    f = f or {}
    # experience shown in the row
    y = d.get('yrs')
    if isinstance(y, (int, float)): d['xp'] = ('<1 yr' if y < 1 else ('%g yrs' % y))
    elif f.get('yb'): d['xp'] = f['yb']
    else: d['xp'] = ''
    # salary: hand-checked text first, then the form
    d['sal'] = d.get('ctc') or f.get('sal') or ''
    # joining: the form's notice period, else whether the resume says they work now
    if f.get('nt'): d['nt'] = f['nt']; d['ntk'] = 'imm' if f['nt'] == 'Immediate' else 'days'
    elif now == 'no': d['nt'] = 'Not working now'; d['ntk'] = 'free'
    elif now == 'yes': d['nt'] = 'Working now'; d['ntk'] = 'work'
    else: d['nt'] = ''; d['ntk'] = ''
    for k in ('tv', 'fmcg', 'fs', 'tm'):
        if f.get(k): d[k] = f[k]
    _stat['co'] += bool(d['co']); _stat['sal'] += bool(d['sal']); _stat['nt_form'] += bool(f.get('nt')); _stat['nt_any'] += bool(d['nt']); _stat['xp'] += bool(d['xp'])
print('row details:', dict(_stat), 'of', len(C))

# old hidden entries have no phone: date them by (unique) name match against the sheets
_byname = collections.defaultdict(set)
for r in json.load(open(os.path.join(SHEETS, 'bde_latest.json')))['values']:
    if len(r) > 2: _byname[clean(r[1])].add(n10(r[2]))
for ts, _n, ph in json.load(open(os.path.join(SHEETS, 'bdm_ts_latest.json'))): _byname[clean(_n)].add(n10(ph))
OLD_HIDDEN = []
for h in sheet['HIDDEN']:
    h = list(h[:3])
    phs = _byname.get(clean(h[0]), set())
    if len(phs) == 1:
        ph = next(iter(phs)); h += [TS.get(ph, ''), TSL.get(ph, ''), TAT.get(ph, ''), wa_number(ph)]
    OLD_HIDDEN.append(h)
data = ''.join([
    jsdump('D', C), jsdump('P', POSOUT), jsdump('HIDDEN', OLD_HIDDEN + new_hidden),
    jsdump('HIDDEN_APP', [[h['n'], h.get('why') or 'Nothing usable', ', '.join(a[1] for a in h['ap'])[:120]] for h in app_hidden]),
    jsdump('NORES', no_resume), jsdump('MISSING', MISSING), jsdump('ISSUES', ISSUES), jsdump('PLAB', PLAB),
])
open(os.path.join(H, 'data.js'), 'w').write(data)

# ---------------------------------------------------------------- report
lv = collections.Counter(c['lv'] for c in C)
src = collections.Counter(c['src'] for c in C)
print('candidates on page', len(C), dict(lv), dict(src), 'merged sheet+app', dup_merged)
print('app hidden', len(app_hidden), ' no resume', len(no_resume))
print('positions', len(POSOUT), 'seats', sum(p['seats'] for p in POSOUT))
for p in POSOUT:
    cnt = collections.Counter(C[m[0]]['lv'] for m in p['m'])
    print(f"{p['st'][:12]:12} {p['title'][:55]:55} S{cnt['strong']:>3} M{cnt['medium']:>3} C{cnt['check']:>3} W{cnt['wait']:>3}")
unknown_loc = sum(1 for c in C if c['src'] == 'A' and not c.get('st'))
print('app candidates with unknown location', unknown_loc)
unmatched = sum(1 for i, c in enumerate(C) if not cand_pos.get(i))
print('candidates matching no open position', unmatched)
