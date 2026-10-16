#!/usr/bin/env python3
"""Run the HR screening page on this computer to test it before pushing.

  python local/serve.py             local mode  -> http://127.0.0.1:8765
  python local/serve.py --reset     local mode, starting with empty local data
  python local/serve.py --live      the page against the real Supabase (exactly what the team sees)
  python local/serve.py --port N    another port (default 8765)

LOCAL MODE (default)
  A small stand-in for Supabase runs inside this server; its data lives in work/local_db.json (not in git).
  Marks, transfers and the Activity log therefore stay on this machine. "Sync leads now" runs the build locally
  (transfers -> dashboard, about 15 seconds) without touching Google Sheets or Claude; the page notices the result
  within a minute, or just reload it. There are no live updates locally, so the red "WebSocket ... failed" lines in
  the browser console are expected. Ctrl+C restores public/index.html and pipeline/app/overrides.json to what they
  were when the server started, so nothing from the test is left in the repo.

LIVE MODE (--live)
  Serves public/ as it is. Marks and transfers go to the real Supabase and are visible to the HR team.
  The Sync button cannot start GitHub from here. To see a live transfer on the dashboard, run with the real
  SUPABASE_URL / SUPABASE_KEY in the environment:
      python pipeline/overrides.py && python pipeline/update.py build && python pipeline/publish.py
  then reload the page (and afterwards `git checkout public/index.html pipeline/app/overrides.json` if you do not want to commit them).

Needs Python 3 with the `requests` package (pip install -r requirements.txt) and internet for the supabase-js CDN.
"""
import datetime, json, os, shutil, subprocess, sys, threading, time, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, 'public')
WORK = os.path.join(ROOT, 'work')
DB_PATH = os.path.join(WORK, 'local_db.json')
BACKUP = os.path.join(WORK, 'local_backup')
KEEP = [os.path.join(PUBLIC, 'index.html'), os.path.join(ROOT, 'pipeline', 'app', 'overrides.json')]
LIVE = '--live' in sys.argv
PORT = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8765
LOCK = threading.Lock()
DB = {'docs': {}, 'activity_log': []}          # docs: "collection\x00id" -> {collection, id, data, updated_at}
SYNC = {'running': False, 'log': []}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def load_db():
    global DB
    try:
        DB = json.load(open(DB_PATH, encoding='utf-8'))
        DB.setdefault('docs', {}); DB.setdefault('activity_log', [])
    except Exception:
        DB = {'docs': {}, 'activity_log': []}


def save_db():
    tmp = DB_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(DB, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DB_PATH)


def backup():
    os.makedirs(BACKUP, exist_ok=True)
    for p in KEEP:
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(BACKUP, os.path.basename(p)))


def restore():
    for p in KEEP:
        b = os.path.join(BACKUP, os.path.basename(p))
        if os.path.exists(b):
            shutil.copy2(b, p)
    print('restored', ', '.join(os.path.relpath(p, ROOT) for p in KEEP), '(as they were when the server started)')


def match(row, filters):
    return all(str(row.get(k, '')) == v for k, v in filters.items())


def run_sync(base):
    """What the GitHub workflow does, minus the Google Sheets and Claude steps (nothing new is fetched or rated)."""
    env = dict(os.environ, PYTHONUTF8='1', SUPABASE_URL=base, SUPABASE_KEY='local', GITHUB_EVENT_NAME='workflow_dispatch',
               RUN_ID='local-' + time.strftime('%Y%m%dT%H%M%S'))
    steps = [('1 - mark started', ['pipeline/runs.py', 'started']),
             ('1b - read transfers', ['pipeline/overrides.py']),
             ('7 - build the page', ['pipeline/update.py', 'build']),
             ('7 - publish', ['pipeline/publish.py']),
             ('9 - mark done', ['pipeline/runs.py', 'done'])]
    SYNC['log'] = []
    try:
        for name, args in steps:
            r = subprocess.run([sys.executable] + args, cwd=ROOT, env=env, capture_output=True, text=True,
                               encoding='utf-8', errors='replace')
            line = '%s: %s' % (name, 'ok' if r.returncode == 0 else 'FAILED')
            SYNC['log'].append(line)
            print('[sync]', line, '-', (r.stdout.strip().splitlines() or [''])[-1][:160])
            if r.returncode:
                print(r.stderr[-2000:])
                err = (r.stderr.strip().splitlines() or ['see the server console'])[-1][:200]
                subprocess.run([sys.executable, 'pipeline/runs.py', 'failed', name, 'Local sync failed at ' + name + ': ' + err],
                               cwd=ROOT, env=env)
                break
    finally:
        SYNC['running'] = False


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=PUBLIC, **k)

    def log_message(self, fmt, *args):
        if self.path.startswith('/rest/') or self.path.startswith('/realtime/'):
            return                                              # keep the console readable
        super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')          # a rebuilt page shows on the next reload
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PATCH, OPTIONS')
        super().end_headers()

    def send_json(self, code, obj=None, extra=None):
        body = b'' if obj is None else json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b''
        return json.loads(raw.decode('utf-8')) if raw.strip() else None

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith('/rest/v1/'):
            return self.rest('GET', u)
        if u.path.startswith('/realtime/'):
            return self.send_json(404, {'error': 'no live updates in local mode'})
        if u.path == '/local/status':
            return self.send_json(200, {'mode': 'live' if LIVE else 'local', 'sync_running': SYNC['running'], 'sync_log': SYNC['log'],
                                        'docs': len(DB['docs']), 'activity_log': len(DB['activity_log'])})
        if u.path == '/config.js' and not LIVE:
            base = 'http://' + self.headers.get('Host', '127.0.0.1:%d' % PORT)
            js = ('/* local test mode: this is not the real Supabase; data stays in work/local_db.json */\n'
                  'window.HR_CONFIG={SUPABASE_URL:%s,SUPABASE_ANON_KEY:"local"};\n' % json.dumps(base)).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(js))); self.end_headers(); self.wfile.write(js)
            return
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == '/api/sync':
            if LIVE:
                return self.send_json(501, {'error': 'This is a local copy of the page; it cannot start GitHub. Run: python pipeline/overrides.py && '
                                                     'python pipeline/update.py build && python pipeline/publish.py, then reload.'})
            if not SYNC['running']:
                SYNC['running'] = True
                threading.Thread(target=run_sync, args=('http://127.0.0.1:%d' % PORT,), daemon=True).start()
            return self.send_json(200, {'ok': True})
        if u.path == '/local/shutdown':
            self.send_json(200, {'ok': True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if u.path.startswith('/rest/v1/'):
            return self.rest('POST', u)
        return self.send_json(404, {'error': 'not found'})

    def do_DELETE(self):
        u = urlparse(self.path)
        if u.path.startswith('/rest/v1/'):
            return self.rest('DELETE', u)
        return self.send_json(404, {'error': 'not found'})

    def do_PATCH(self):
        return self.send_json(405, {'error': 'not used by the page'})

    def rest(self, method, u):
        """Just enough of the Supabase REST API (PostgREST) for the page, runs.py and overrides.py."""
        table = u.path[len('/rest/v1/'):]
        if table not in ('docs', 'activity_log'):
            return self.send_json(404, {'message': 'unknown table ' + table})
        q = parse_qs(u.query)
        filters = {k: v[0][3:] for k, v in q.items() if v and v[0].startswith('eq.')}
        with LOCK:
            rows = list(DB['docs'].values()) if table == 'docs' else list(DB['activity_log'])
            rows = [r for r in rows if match(r, filters)]
            if method == 'GET':
                key, _, direction = (q.get('order') or ['id.asc'])[0].partition('.')
                rows.sort(key=lambda r: str(r.get(key, '')), reverse=(direction == 'desc'))
                start, stop = 0, len(rows)
                rng = self.headers.get('Range')                 # supabase-js .range(a, b)
                if rng and '-' in rng:
                    a, b = rng.split('-', 1)
                    start = int(a or 0); stop = int(b) + 1 if b else stop
                if 'offset' in q: start = int(q['offset'][0])  # overrides.py
                if 'limit' in q: stop = start + int(q['limit'][0])
                part = rows[start:stop]
                return self.send_json(200, part, {'Content-Range': ('%d-%d/*' % (start, start + len(part) - 1)) if part else '*/0'})
            if method == 'POST':
                data = self.body()
                for it in (data if isinstance(data, list) else [data]):
                    if not isinstance(it, dict):
                        continue
                    if table == 'docs':                        # upsert on (collection, id)
                        it.setdefault('updated_at', now())
                        DB['docs'][str(it.get('collection')) + '\x00' + str(it.get('id'))] = it
                    else:                                       # insert-only log
                        it.setdefault('id', str(uuid.uuid4())); it.setdefault('at', now())
                        for k in ('who', 'cand', 'phone', 'pos', 'old_value', 'new_value', 'reason'):
                            it.setdefault(k, '')
                        DB['activity_log'].append(it)
                save_db()
                return self.send_json(201)
            if method == 'DELETE':
                if table == 'docs':
                    for r in rows:
                        DB['docs'].pop(str(r.get('collection')) + '\x00' + str(r.get('id')), None)
                else:
                    DB['activity_log'] = [r for r in DB['activity_log'] if r not in rows]
                save_db()
                return self.send_json(204)
        return self.send_json(405)


def main():
    os.makedirs(WORK, exist_ok=True)
    if '--reset' in sys.argv and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print('local data cleared')
    if not LIVE:
        load_db()
        backup()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    url = 'http://127.0.0.1:%d/' % PORT
    print('HR screening page:', url, '(also http://localhost:%d/)' % PORT)
    if LIVE:
        print('LIVE mode: marks and transfers go to the REAL Supabase and are visible to the HR team. Ctrl+C to stop.')
    else:
        print('LOCAL mode: marks, transfers and the Activity log stay in work/local_db.json (%d docs, %d log rows).'
              % (len(DB['docs']), len(DB['activity_log'])))
        print('"Sync leads now" rebuilds the page locally (transfers -> dashboard). Ctrl+C stops and restores the repo files.')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        if not LIVE:
            restore()


if __name__ == '__main__':
    main()
